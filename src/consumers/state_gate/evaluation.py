from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from orchestrator.contracts import EngineMode
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.state import HysteresisState

from .assembly import AssembledRunInput
from .config import StateGateConfig
from .contracts import (
    GATE_STATUS_CLOSED,
    GATE_STATUS_OPEN,
    REASON_CODE_RUN_FAILED,
    REASON_CODE_TRANSITION_ACTIVE,
    REASON_PREFIX_DENYLISTED_INVALIDATION,
    STATE_STATUS_DEGRADED,
    STATE_STATUS_HOLD,
    STATE_STATUS_READY,
    GateStatus,
    InputEventType,
    StateStatus,
)


@dataclass(frozen=True)
class GateEvaluation:
    gate_status: GateStatus
    state_status: StateStatus
    reasons: Sequence[str]
    input_event_type: InputEventType
    engine_mode: EngineMode | None
    regime_output: RegimeOutput | None = None
    hysteresis_state: HysteresisState | None = None


class GateEvaluator:
    def __init__(self, *, config: StateGateConfig) -> None:
        self._config = config
        self._denylist = set(config.denylisted_invalidations)

    def evaluate(self, run: AssembledRunInput) -> GateEvaluation:
        failure_eval = self._maybe_failure(run)
        if failure_eval is not None:
            return failure_eval

        denylist_eval = self._maybe_denylisted(run)
        if denylist_eval is not None:
            return denylist_eval

        transition_eval = self._maybe_transition_hold(run)
        if transition_eval is not None:
            return transition_eval

        return self._open_gate(run)

    def _maybe_failure(self, run: AssembledRunInput) -> GateEvaluation | None:
        if run.input_event_type != "EngineRunFailed":
            return None
        return GateEvaluation(
            gate_status=GATE_STATUS_CLOSED,
            state_status=STATE_STATUS_DEGRADED,
            reasons=[REASON_CODE_RUN_FAILED],
            input_event_type=run.input_event_type,
            engine_mode=run.engine_mode,
        )

    def _maybe_denylisted(self, run: AssembledRunInput) -> GateEvaluation | None:
        if run.regime_output is None:
            return None
        matched = {
            invalidation
            for invalidation in run.regime_output.invalidations
            if invalidation in self._denylist
        }
        if not matched:
            return None
        reasons = sorted(
            f"{REASON_PREFIX_DENYLISTED_INVALIDATION}{value}"
            for value in matched
        )
        return GateEvaluation(
            gate_status=GATE_STATUS_CLOSED,
            state_status=STATE_STATUS_HOLD,
            reasons=reasons,
            input_event_type=run.input_event_type,
            engine_mode=run.engine_mode,
            regime_output=run.regime_output,
        )

    def _maybe_transition_hold(self, run: AssembledRunInput) -> GateEvaluation | None:
        hysteresis_state = run.hysteresis_state
        if hysteresis_state is None:
            return None
        if not self._config.block_during_transition:
            return None
        if hysteresis_state.progress_current <= 0:
            return None
        return GateEvaluation(
            gate_status=GATE_STATUS_CLOSED,
            state_status=STATE_STATUS_HOLD,
            reasons=[REASON_CODE_TRANSITION_ACTIVE],
            input_event_type=run.input_event_type,
            engine_mode=run.engine_mode,
            regime_output=run.regime_output,
            hysteresis_state=hysteresis_state,
        )

    def _open_gate(self, run: AssembledRunInput) -> GateEvaluation:
        if run.hysteresis_state is not None:
            return GateEvaluation(
                gate_status=GATE_STATUS_OPEN,
                state_status=STATE_STATUS_READY,
                reasons=[],
                input_event_type=run.input_event_type,
                engine_mode=run.engine_mode,
                regime_output=run.regime_output,
                hysteresis_state=run.hysteresis_state,
            )
        return GateEvaluation(
            gate_status=GATE_STATUS_OPEN,
            state_status=STATE_STATUS_READY,
            reasons=[],
            input_event_type=run.input_event_type,
            engine_mode=run.engine_mode,
            regime_output=run.regime_output,
        )
