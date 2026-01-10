from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from composer.engine_evidence.compute import compute_engine_evidence_snapshot
from composer.features.compute import compute_feature_snapshot
from composer.legacy_snapshot import build_legacy_snapshot
from consumers.analysis_engine import AnalysisEngine, AnalysisEngineConfig
from consumers.analysis_engine.contracts import AnalysisEngineEvent
from consumers.analysis_engine.observability import NullMetrics as AnalysisNullMetrics
from consumers.analysis_engine.observability import Observability as AnalysisObservability
from consumers.analysis_engine.observability import StdlibLogger as AnalysisStdlibLogger
from consumers.analysis_engine.registry import ModuleRegistry
from consumers.dashboards import DashboardBuilder, TuiRenderer
from consumers.dashboards.observability import NullMetrics as DashNullMetrics
from consumers.dashboards.observability import Observability as DashObservability
from consumers.dashboards.observability import StdlibLogger as DashStdlibLogger
from consumers.state_gate import StateGateConfig, StateGateProcessor
from consumers.state_gate.config import OperationLimits
from consumers.state_gate.contracts import StateGateEvent
from consumers.state_gate.observability import NullMetrics as GateNullMetrics
from consumers.state_gate.observability import Observability as GateObservability
from consumers.state_gate.observability import StdlibLogger as GateStdlibLogger
from market_data.contracts import RawMarketEvent
from market_data.pipeline import emit_cadence_summary
from orchestrator.buffer import RawInputBuffer
from orchestrator.config import SchedulerConfig
from orchestrator.contracts import (
    ENGINE_MODE_HYSTERESIS,
    ENGINE_MODE_TRUTH,
    CutKind,
    EngineMode,
    EngineRunRecord,
    OrchestratorEvent,
)
from orchestrator.cuts import CutSelector
from orchestrator.engine_runner import (
    EngineRunner,
    HysteresisMonotonicityError,
    HysteresisPersistenceError,
    HysteresisStatePersistence,
)
from orchestrator.observability import NullMetrics as OrchestratorNullMetrics
from orchestrator.observability import Observability as OrchestratorObservability
from orchestrator.observability import StdlibLogger as OrchestratorStdlibLogger
from orchestrator.publisher import (
    OrchestratorEventPublisher,
    build_engine_run_completed,
    build_engine_run_failed,
    build_engine_run_started,
    build_hysteresis_state_published,
)
from orchestrator.run_id import derive_run_id
from orchestrator.run_records import EngineRunLog
from orchestrator.scheduler import Scheduler
from orchestrator.sequencing import SymbolSequencer
from regime_engine.hysteresis import HysteresisConfig
from runtime.bus import EventBus


class BusEventSink:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def write(self, event: object) -> None:
        self._bus.publish(event)


class OrchestratorRuntime:
    def __init__(
        self,
        *,
        bus: EventBus,
        engine_mode: EngineMode = ENGINE_MODE_TRUTH,
        hysteresis_state_path: str | None = None,
        hysteresis_config: HysteresisConfig | None = None,
        observability: OrchestratorObservability | None = None,
        scheduler_config: SchedulerConfig | None = None,
    ) -> None:
        self._buffer = RawInputBuffer(max_records=50_000)
        self._cut_selector = CutSelector()
        self._engine_mode: EngineMode = engine_mode
        self._symbols: set[str] = set()
        self._observability = observability or OrchestratorObservability(
            logger=OrchestratorStdlibLogger(logging.getLogger("orchestrator")),
            metrics=OrchestratorNullMetrics(),
        )
        hysteresis_store = None
        hysteresis_config = hysteresis_config or HysteresisConfig()
        if engine_mode == ENGINE_MODE_HYSTERESIS:
            if hysteresis_state_path is None:
                raise ValueError("hysteresis_state_path is required for hysteresis mode")
            hysteresis_store = HysteresisStatePersistence.restore(
                path=hysteresis_state_path,
                config=hysteresis_config,
            )
        self._engine_runner = EngineRunner(
            engine_mode=engine_mode,
            hysteresis_store=hysteresis_store,
            hysteresis_config=hysteresis_config,
            observability=self._observability,
        )
        self._publisher = OrchestratorEventPublisher(
            sink=BusEventSink(bus), sequencer=SymbolSequencer()
        )
        self._scheduler = Scheduler(
            scheduler_config
            or SchedulerConfig(mode="boundary", boundary_interval_ms=180_000, boundary_delay_ms=0)
        )
        self._run_log = EngineRunLog()
        self._scheduler_running = False
        self._scheduler_thread: threading.Thread | None = None

    def start(self) -> None:
        if self._scheduler_running:
            return
        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler, name="orchestrator-scheduler", daemon=True
        )
        self._scheduler_thread.start()

    def stop(self) -> None:
        self._scheduler_running = False
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=1)

    def handle_raw_event(self, event: RawMarketEvent) -> None:
        self._buffer.append(event)
        self._symbols.add(event.symbol)

    def _run_scheduler(self) -> None:
        while self._scheduler_running:
            now_ms = _now_ms()
            planned_ts_ms = self._scheduler.next_tick_ms(now_ms=now_ms)
            delay_ms = max(0, planned_ts_ms - now_ms)
            if delay_ms > 0:
                time.sleep(delay_ms / 1000)
            self._run_due(planned_ts_ms=planned_ts_ms)

    def _run_due(self, *, planned_ts_ms: int) -> None:
        latest_seq = self._cut_selector.latest_ingest_seq(self._buffer)
        if latest_seq is None:
            return
        symbols = sorted(self._symbols)
        if not symbols:
            return
        cut_kind: CutKind = "boundary" if self._scheduler.config.mode == "boundary" else "timer"
        engine_timestamp_ms = _engine_timestamp_ms(self._scheduler.config, planned_ts_ms)
        for symbol in symbols:
            if self._guard_hysteresis_monotonic(symbol, engine_timestamp_ms):
                self._scheduler_running = False
                return
            emit_cadence_summary(symbol)
            try:
                cut = self._cut_selector.next_cut(
                    buffer=self._buffer,
                    symbol=symbol,
                    cut_end_ingest_seq=latest_seq,
                    cut_kind=cut_kind,
                )
            except ValueError:
                continue
            run_id = derive_run_id(
                symbol=symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                engine_mode=self._engine_mode,
            )
            run_record = EngineRunRecord(
                run_id=run_id,
                symbol=symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                engine_mode=self._engine_mode,
                cut_kind=cut_kind,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                planned_ts_ms=planned_ts_ms,
                started_ts_ms=_now_ms(),
                completed_ts_ms=None,
                status="started",
                attempts=1,
            )
            self._run_log.append(run_record)
            started = build_engine_run_started(
                run_id=run_id,
                symbol=symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                cut_kind=cut_kind,
                engine_mode=self._engine_mode,
                attempt=1,
            )
            self._publisher.publish(started)
            raw_events = _raw_events_for_cut(
                buffer=self._buffer,
                symbol=symbol,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
            )
            counts_by_event_type = _counts_by_event_type(raw_events)
            try:
                feature_snapshot = compute_feature_snapshot(
                    raw_events,
                    symbol=symbol,
                    engine_timestamp_ms=engine_timestamp_ms,
                )
                evidence_snapshot = compute_engine_evidence_snapshot(feature_snapshot)
                snapshot = build_legacy_snapshot(
                    raw_events,
                    symbol=symbol,
                    engine_timestamp_ms=engine_timestamp_ms,
                    feature_snapshot=feature_snapshot,
                    evidence_snapshot=evidence_snapshot,
                )
            except Exception as exc:
                failed = build_engine_run_failed(
                    run_id=run_id,
                    symbol=symbol,
                    engine_timestamp_ms=engine_timestamp_ms,
                    cut_start_ingest_seq=cut.cut_start_ingest_seq,
                    cut_end_ingest_seq=cut.cut_end_ingest_seq,
                    cut_kind=cut_kind,
                    engine_mode=self._engine_mode,
                    error_kind="snapshot_build_failure",
                    error_detail=str(exc),
                    attempt=1,
                    counts_by_event_type=counts_by_event_type,
                )
                self._publisher.publish(failed)
                continue
            try:
                result = self._engine_runner.run_engine(snapshot)
            except (HysteresisPersistenceError, HysteresisMonotonicityError):
                self._scheduler_running = False
                return
            except Exception as exc:
                failed = build_engine_run_failed(
                    run_id=run_id,
                    symbol=symbol,
                    engine_timestamp_ms=engine_timestamp_ms,
                    cut_start_ingest_seq=cut.cut_start_ingest_seq,
                    cut_end_ingest_seq=cut.cut_end_ingest_seq,
                    cut_kind=cut_kind,
                    engine_mode=self._engine_mode,
                    error_kind="engine_failure",
                    error_detail=str(exc),
                    attempt=1,
                    counts_by_event_type=counts_by_event_type,
                )
                self._publisher.publish(failed)
                continue

            if result.hysteresis_state is not None:
                decision_event = build_hysteresis_state_published(
                    run_id=run_id,
                    symbol=symbol,
                    engine_timestamp_ms=engine_timestamp_ms,
                    cut_start_ingest_seq=cut.cut_start_ingest_seq,
                    cut_end_ingest_seq=cut.cut_end_ingest_seq,
                    cut_kind=cut_kind,
                    hysteresis_state=result.hysteresis_state,
                    attempt=1,
                    counts_by_event_type=counts_by_event_type,
                )
                self._publisher.publish(decision_event)
            regime_output = result.regime_output

            completed = build_engine_run_completed(
                run_id=run_id,
                symbol=symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                cut_kind=cut_kind,
                engine_mode=self._engine_mode,
                regime_output=regime_output,
                attempt=1,
                counts_by_event_type=counts_by_event_type,
            )
            self._publisher.publish(completed)

    def _guard_hysteresis_monotonic(self, symbol: str, engine_timestamp_ms: int) -> bool:
        if self._engine_mode != ENGINE_MODE_HYSTERESIS:
            return False
        store = self._engine_runner.hysteresis_store
        if store is None:
            return False
        prev_state = store.store.state_for(symbol)
        if prev_state is None:
            return False
        if engine_timestamp_ms < prev_state.engine_timestamp_ms:
            return True
        return False


class DashboardRuntime:
    def __init__(self, *, builder: DashboardBuilder, renderer: TuiRenderer) -> None:
        self._builder = builder
        self._renderer = renderer

    def start(self) -> None:
        self._renderer.start()

    def stop(self) -> None:
        self._renderer.stop()

    def render_once(self) -> None:
        self._render()

    def handle_orchestrator(self, event: OrchestratorEvent) -> None:
        self._builder.ingest_orchestrator_event(event)
        self._render()

    def handle_state_gate(self, event: StateGateEvent) -> None:
        self._builder.ingest_state_gate_event(event)
        self._render()

    def handle_analysis_engine(self, event: AnalysisEngineEvent) -> None:
        self._builder.ingest_analysis_engine_event(event)
        self._render()

    def _render(self) -> None:
        snapshot = self._builder.build_snapshot()
        self._renderer.render(snapshot)


@dataclass(frozen=True)
class RuntimeWiring:
    orchestrator: OrchestratorRuntime
    state_gate: StateGateProcessor
    analysis_engine: AnalysisEngine
    dashboards: DashboardRuntime


def build_runtime(bus: EventBus) -> RuntimeWiring:
    orchestrator = OrchestratorRuntime(
        bus=bus,
        observability=OrchestratorObservability(
            logger=OrchestratorStdlibLogger(logging.getLogger("orchestrator")),
            metrics=OrchestratorNullMetrics(),
        ),
    )
    state_gate = StateGateProcessor(
        config=StateGateConfig(
            max_gap_ms=180_000,
            denylisted_invalidations=(),
            block_during_transition=False,
            input_limits=OperationLimits(max_pending=1_000),
            persistence_limits=OperationLimits(max_pending=1_000),
            publish_limits=OperationLimits(max_pending=1_000),
        ),
        observability=GateObservability(
            logger=GateStdlibLogger(logging.getLogger("consumers.state_gate")),
            metrics=GateNullMetrics(),
        ),
    )
    registry = ModuleRegistry(modules=())
    analysis_engine = AnalysisEngine(
        registry=registry,
        config=AnalysisEngineConfig(enabled_modules=(), module_configs=()),
        observability=AnalysisObservability(
            logger=AnalysisStdlibLogger(logging.getLogger("consumers.analysis_engine")),
            metrics=AnalysisNullMetrics(),
        ),
    )
    dashboards_observability = DashObservability(
        logger=DashStdlibLogger(logging.getLogger("consumers.dashboards")),
        metrics=DashNullMetrics(),
    )
    dashboards = DashboardRuntime(
        builder=DashboardBuilder(observability=dashboards_observability),
        renderer=TuiRenderer(observability=dashboards_observability),
    )
    return RuntimeWiring(
        orchestrator=orchestrator,
        state_gate=state_gate,
        analysis_engine=analysis_engine,
        dashboards=dashboards,
    )


def register_subscriptions(bus: EventBus, runtime: RuntimeWiring) -> None:
    bus.subscribe(RawMarketEvent, runtime.orchestrator.handle_raw_event)

    def handle_orchestrator(event: OrchestratorEvent) -> None:
        for state_event in runtime.state_gate.consume(event):
            bus.publish(state_event)
        runtime.dashboards.handle_orchestrator(event)

    def handle_state_gate(event: StateGateEvent) -> None:
        for analysis_event in runtime.analysis_engine.consume(event):
            bus.publish(analysis_event)
        runtime.dashboards.handle_state_gate(event)

    def handle_analysis_engine(event: AnalysisEngineEvent) -> None:
        runtime.dashboards.handle_analysis_engine(event)

    bus.subscribe(OrchestratorEvent, handle_orchestrator)
    bus.subscribe(StateGateEvent, handle_state_gate)
    bus.subscribe(AnalysisEngineEvent, handle_analysis_engine)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _engine_timestamp_ms(config: SchedulerConfig, planned_ts_ms: int) -> int:
    if config.mode == "boundary":
        delay_ms = config.boundary_delay_ms or 0
        return planned_ts_ms - delay_ms
    return planned_ts_ms


def _raw_events_for_cut(
    *,
    buffer: RawInputBuffer,
    symbol: str,
    cut_start_ingest_seq: int,
    cut_end_ingest_seq: int,
) -> tuple[RawMarketEvent, ...]:
    records = buffer.range_by_symbol(
        symbol=symbol,
        start_seq=cut_start_ingest_seq,
        end_seq=cut_end_ingest_seq,
    )
    return tuple(record.event for record in records)


def _counts_by_event_type(raw_events: tuple[RawMarketEvent, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in raw_events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    return counts
