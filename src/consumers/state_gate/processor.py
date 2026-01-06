from __future__ import annotations

from typing import List

from orchestrator.contracts import OrchestratorEvent

from .assembly import RunAssembler
from .config import StateGateConfig
from .contracts import (
    GATE_STATUS_CLOSED,
    REASON_CODE_INTERNAL_FAILURE,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    StateGateEvent,
    StateGateHaltedPayload,
    StateGateSnapshot,
    StateGateStateRecord,
    STATE_STATUS_HALTED,
)
from .evaluation import GateEvaluator
from .observability import HealthStatus, NullLogger, NullMetrics, Observability
from .state_machine import StateGateStateMachine
from .state_store import StateGateStateStore


class StateGateProcessor:
    def __init__(
        self,
        *,
        config: StateGateConfig,
        store: StateGateStateStore | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._config = config
        self._store = store or StateGateStateStore()
        self._assembler = RunAssembler(
            processed_run_ids=self._store.processed_run_ids(),
            latest_engine_timestamp_ms=self._store.latest_engine_timestamps(),
        )
        self._evaluator = GateEvaluator(config=config)
        self._state_machine = StateGateStateMachine(config=config, snapshots=self._store.snapshots())
        self._observability = observability or Observability(logger=NullLogger(), metrics=NullMetrics())
        self._halted = False
        self._input_healthy = True
        self._persistence_healthy = True
        self._publish_healthy = True

    def consume(self, event: OrchestratorEvent) -> List[StateGateEvent]:
        if self._halted:
            return []
        assembled = self._assembler.ingest(event)
        if assembled is None:
            return []
        previous_snapshot = self._store.snapshot_for(assembled.symbol)
        evaluation = self._evaluator.evaluate(assembled)
        events = self._state_machine.process_run(assembled, evaluation)
        if self._publish_blocked(len(events)):
            halt_event = self._enter_halted(
                symbol=assembled.symbol,
                run_id=assembled.run_id,
                engine_timestamp_ms=assembled.engine_timestamp_ms,
                input_event_type=assembled.input_event_type,
                engine_mode=assembled.engine_mode,
                error_kind="publish_blocked",
                error_detail="output publish backpressure exceeded",
                persist=True,
            )
            return [halt_event]
        for event in events:
            try:
                self._store.append_event(event)
            except Exception as exc:  # pragma: no cover - defensive guard
                self._persistence_healthy = False
                halt_event = self._enter_halted(
                    symbol=event.symbol,
                    run_id=event.run_id,
                    engine_timestamp_ms=event.engine_timestamp_ms,
                    input_event_type=event.input_event_type,
                    engine_mode=event.engine_mode,
                    error_kind="persistence_failure",
                    error_detail=str(exc),
                    persist=False,
                )
                return [halt_event]
            processing_lag = _processing_lag_ms(event, previous_snapshot)
            self._observability.log_event(event)
            self._observability.record_metrics(event, processing_lag_ms=processing_lag)
        return events

    def snapshot_for(self, symbol: str) -> StateGateSnapshot:
        return self._store.snapshot_for(symbol)

    def records(self) -> List[StateGateStateRecord]:
        return list(self._store.records())

    def state_store(self) -> StateGateStateStore:
        return self._store

    def health_status(self) -> HealthStatus:
        ready = all(
            [
                not self._halted,
                self._input_healthy,
                self._persistence_healthy,
                self._publish_healthy,
            ]
        )
        return HealthStatus(
            ready=ready,
            halted=self._halted,
            input_healthy=self._input_healthy,
            persistence_healthy=self._persistence_healthy,
            publish_healthy=self._publish_healthy,
        )

    def _publish_blocked(self, event_count: int) -> bool:
        return event_count > self._config.publish_limits.max_pending

    def _enter_halted(
        self,
        *,
        symbol: str,
        run_id: str,
        engine_timestamp_ms: int,
        input_event_type: str | None,
        engine_mode: str | None,
        error_kind: str,
        error_detail: str,
        persist: bool,
    ) -> StateGateEvent:
        self._halted = True
        self._publish_healthy = False
        if not persist:
            self._persistence_healthy = False
        halt_event = StateGateEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type="StateGateHalted",
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            run_id=run_id,
            state_status=STATE_STATUS_HALTED,
            gate_status=GATE_STATUS_CLOSED,
            reasons=[REASON_CODE_INTERNAL_FAILURE],
            payload=StateGateHaltedPayload(error_kind=error_kind, error_detail=error_detail),
            input_event_type=input_event_type,
            engine_mode=engine_mode,
        )
        if persist:
            try:
                self._store.append_event(halt_event)
            except Exception:  # pragma: no cover - defensive guard
                self._persistence_healthy = False
        self._observability.log_event(halt_event)
        self._observability.record_metrics(halt_event, processing_lag_ms=None)
        return halt_event


def _processing_lag_ms(event: StateGateEvent, previous_snapshot: StateGateSnapshot) -> int | None:
    if event.event_type != "GateEvaluated":
        return None
    if previous_snapshot.last_engine_timestamp_ms is None:
        return None
    return event.engine_timestamp_ms - previous_snapshot.last_engine_timestamp_ms
