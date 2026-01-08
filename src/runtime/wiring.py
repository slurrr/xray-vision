from __future__ import annotations

from dataclasses import dataclass

from consumers.analysis_engine import AnalysisEngine, AnalysisEngineConfig
from consumers.analysis_engine.contracts import AnalysisEngineEvent
from consumers.analysis_engine.registry import ModuleRegistry
from consumers.dashboards import DashboardBuilder, TuiRenderer
from consumers.state_gate import StateGateConfig, StateGateProcessor
from consumers.state_gate.config import OperationLimits
from consumers.state_gate.contracts import StateGateEvent
from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.contracts import ENGINE_MODE_TRUTH, CutKind, EngineMode, OrchestratorEvent
from orchestrator.cuts import CutSelector
from orchestrator.engine_runner import EngineRunner
from orchestrator.publisher import (
    OrchestratorEventPublisher,
    build_engine_run_completed,
    build_engine_run_failed,
    build_engine_run_started,
    build_hysteresis_state_published,
)
from orchestrator.run_id import derive_run_id
from orchestrator.sequencing import SymbolSequencer
from orchestrator.snapshots import build_snapshot, select_snapshot_event
from runtime.bus import EventBus


class BusEventSink:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def write(self, event: object) -> None:
        self._bus.publish(event)


class OrchestratorRuntime:
    def __init__(
        self, *, bus: EventBus, engine_mode: EngineMode = ENGINE_MODE_TRUTH
    ) -> None:
        self._buffer = RawInputBuffer(max_records=50_000)
        self._cut_selector = CutSelector()
        self._engine_mode: EngineMode = engine_mode
        self._engine_runner = EngineRunner(engine_mode=engine_mode)
        self._publisher = OrchestratorEventPublisher(
            sink=BusEventSink(bus), sequencer=SymbolSequencer()
        )

    def handle_raw_event(self, event: RawMarketEvent) -> None:
        record = self._buffer.append(event)
        if event.event_type != "SnapshotInputs":
            return
        timestamp_value = event.normalized.get("timestamp_ms")
        if not isinstance(timestamp_value, int) or isinstance(timestamp_value, bool):
            return
        engine_timestamp_ms = timestamp_value
        cut_kind: CutKind = "boundary"
        cut = self._cut_selector.next_cut(
            buffer=self._buffer,
            symbol=event.symbol,
            cut_end_ingest_seq=record.ingest_seq,
            cut_kind=cut_kind,
        )
        run_id = derive_run_id(
            symbol=event.symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            cut_end_ingest_seq=cut.cut_end_ingest_seq,
            engine_mode=self._engine_mode,
        )
        started = build_engine_run_started(
            run_id=run_id,
            symbol=event.symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            cut_start_ingest_seq=cut.cut_start_ingest_seq,
            cut_end_ingest_seq=cut.cut_end_ingest_seq,
            cut_kind=cut_kind,
            engine_mode=self._engine_mode,
            attempt=1,
        )
        self._publisher.publish(started)
        snapshot_event = select_snapshot_event(
            buffer=self._buffer, cut=cut, engine_timestamp_ms=engine_timestamp_ms
        )
        if snapshot_event is None:
            failed = build_engine_run_failed(
                run_id=run_id,
                symbol=event.symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                cut_kind=cut_kind,
                engine_mode=self._engine_mode,
                error_kind="missing_snapshot_inputs",
                error_detail="missing SnapshotInputs",
                attempt=1,
            )
            self._publisher.publish(failed)
            return
        snapshot = build_snapshot(
            symbol=event.symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            snapshot_event=snapshot_event,
        )
        try:
            result = self._engine_runner.run_engine(snapshot)
        except Exception as exc:
            failed = build_engine_run_failed(
                run_id=run_id,
                symbol=event.symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                cut_kind=cut_kind,
                engine_mode=self._engine_mode,
                error_kind="engine_failure",
                error_detail=str(exc),
                attempt=1,
            )
            self._publisher.publish(failed)
            return

        if result.hysteresis_state is not None:
            decision_event = build_hysteresis_state_published(
                run_id=run_id,
                symbol=event.symbol,
                engine_timestamp_ms=engine_timestamp_ms,
                cut_start_ingest_seq=cut.cut_start_ingest_seq,
                cut_end_ingest_seq=cut.cut_end_ingest_seq,
                cut_kind=cut_kind,
                hysteresis_state=result.hysteresis_state,
                attempt=1,
            )
            self._publisher.publish(decision_event)
        regime_output = result.regime_output

        completed = build_engine_run_completed(
            run_id=run_id,
            symbol=event.symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            cut_start_ingest_seq=cut.cut_start_ingest_seq,
            cut_end_ingest_seq=cut.cut_end_ingest_seq,
            cut_kind=cut_kind,
            engine_mode=self._engine_mode,
            regime_output=regime_output,
            attempt=1,
        )
        self._publisher.publish(completed)


class DashboardRuntime:
    def __init__(self, *, builder: DashboardBuilder, renderer: TuiRenderer) -> None:
        self._builder = builder
        self._renderer = renderer

    def start(self) -> None:
        self._renderer.start()

    def stop(self) -> None:
        self._renderer.stop()

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
    orchestrator = OrchestratorRuntime(bus=bus)
    state_gate = StateGateProcessor(
        config=StateGateConfig(
            max_gap_ms=60_000,
            denylisted_invalidations=(),
            block_during_transition=False,
            input_limits=OperationLimits(max_pending=1_000),
            persistence_limits=OperationLimits(max_pending=1_000),
            publish_limits=OperationLimits(max_pending=1_000),
        )
    )
    registry = ModuleRegistry(modules=())
    analysis_engine = AnalysisEngine(
        registry=registry,
        config=AnalysisEngineConfig(enabled_modules=(), module_configs=()),
    )
    dashboards = DashboardRuntime(builder=DashboardBuilder(), renderer=TuiRenderer())
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
