from __future__ import annotations

from typing import Dict, List, Mapping

from orchestrator.contracts import EngineMode

from .assembly import AssembledRunInput
from .config import StateGateConfig
from .contracts import (
    EVENT_TYPE_GATE_EVALUATED,
    EVENT_TYPE_STATE_RESET,
    GATE_STATUS_CLOSED,
    GateEvaluatedPayload,
    StateGateEvent,
    StateGateSnapshot,
    StateResetPayload,
    STATE_STATUS_BOOTSTRAP,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    RESET_REASON_ENGINE_GAP,
    RESET_REASON_TIMESTAMP_GAP,
)
from .evaluation import GateEvaluation


class StateGateStateMachine:
    def __init__(self, *, config: StateGateConfig, snapshots: Mapping[str, StateGateSnapshot] | None = None) -> None:
        self._config = config
        self._snapshots: Dict[str, StateGateSnapshot] = dict(snapshots) if snapshots else {}

    def process_run(self, run: AssembledRunInput, evaluation: GateEvaluation) -> List[StateGateEvent]:
        snapshot = self._snapshots.get(run.symbol, _bootstrap_snapshot(symbol=run.symbol))
        events: List[StateGateEvent] = []

        reset_reason = self._detect_reset(run=run, snapshot=snapshot)
        if reset_reason is not None:
            reset_event = self._build_reset_event(run=run, reset_reason=reset_reason, engine_mode=evaluation.engine_mode)
            events.append(reset_event)
            snapshot = _bootstrap_snapshot(symbol=run.symbol)
            self._snapshots[run.symbol] = snapshot

        gate_event = self._build_gate_event(run=run, evaluation=evaluation)
        events.append(gate_event)
        self._snapshots[run.symbol] = StateGateSnapshot(
            symbol=run.symbol,
            last_run_id=run.run_id,
            last_engine_timestamp_ms=run.engine_timestamp_ms,
            state_status=evaluation.state_status,
            gate_status=evaluation.gate_status,
            reasons=list(evaluation.reasons),
            engine_mode=evaluation.engine_mode,
            source_event_type=evaluation.input_event_type,
        )
        return events

    def snapshot_for(self, symbol: str) -> StateGateSnapshot:
        return self._snapshots.get(symbol, _bootstrap_snapshot(symbol=symbol))

    def _detect_reset(self, *, run: AssembledRunInput, snapshot: StateGateSnapshot) -> str | None:
        if run.hysteresis_decision is not None and run.hysteresis_decision.transition.reset_due_to_gap:
            return RESET_REASON_ENGINE_GAP

        last_timestamp = snapshot.last_engine_timestamp_ms
        if last_timestamp is None:
            return None

        if run.engine_timestamp_ms - last_timestamp > self._config.max_gap_ms:
            return RESET_REASON_TIMESTAMP_GAP
        return None

    def _build_reset_event(
        self,
        *,
        run: AssembledRunInput,
        reset_reason: str,
        engine_mode: EngineMode | None,
    ) -> StateGateEvent:
        return StateGateEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type=EVENT_TYPE_STATE_RESET,
            symbol=run.symbol,
            engine_timestamp_ms=run.engine_timestamp_ms,
            run_id=run.run_id,
            state_status=STATE_STATUS_BOOTSTRAP,
            gate_status=GATE_STATUS_CLOSED,
            reasons=[reset_reason],
            payload=StateResetPayload(reset_reason=reset_reason),
            input_event_type=run.input_event_type,
            engine_mode=engine_mode,
        )

    def _build_gate_event(self, *, run: AssembledRunInput, evaluation: GateEvaluation) -> StateGateEvent:
        payload: GateEvaluatedPayload | None = None
        if evaluation.regime_output is not None or evaluation.hysteresis_decision is not None:
            payload = GateEvaluatedPayload(
                regime_output=evaluation.regime_output,
                hysteresis_decision=evaluation.hysteresis_decision,
            )
        return StateGateEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type=EVENT_TYPE_GATE_EVALUATED,
            symbol=run.symbol,
            engine_timestamp_ms=run.engine_timestamp_ms,
            run_id=run.run_id,
            state_status=evaluation.state_status,
            gate_status=evaluation.gate_status,
            reasons=list(evaluation.reasons),
            payload=payload,
            input_event_type=evaluation.input_event_type,
            engine_mode=evaluation.engine_mode,
        )


def _bootstrap_snapshot(*, symbol: str) -> StateGateSnapshot:
    return StateGateSnapshot(
        symbol=symbol,
        last_run_id=None,
        last_engine_timestamp_ms=None,
        state_status=STATE_STATUS_BOOTSTRAP,
        gate_status=GATE_STATUS_CLOSED,
        reasons=[],
        engine_mode=None,
        source_event_type=None,
    )
