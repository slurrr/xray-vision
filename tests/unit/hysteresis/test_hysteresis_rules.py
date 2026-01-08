import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.rules import advance_hysteresis, select_candidate
from regime_engine.hysteresis.state import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    HysteresisConfig,
    HysteresisState,
)
from regime_engine.state.state import RegimeState


def _belief(values: dict[Regime, float]) -> dict[Regime, float]:
    belief = {regime: 0.0 for regime in Regime}
    belief.update(values)
    return belief


def _regime_state(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    anchor_regime: Regime,
    belief_by_regime: dict[Regime, float],
) -> RegimeState:
    return RegimeState(
        schema="regime_state",
        schema_version="1",
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        belief_by_regime=belief_by_regime,
        anchor_regime=anchor_regime,
    )


def _hysteresis_state(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    anchor_regime: Regime,
    candidate_regime: Regime | None,
    progress_current: int,
    progress_required: int,
    reason_codes: tuple[str, ...] = (),
    last_commit_timestamp_ms: int | None = None,
) -> HysteresisState:
    return HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        anchor_regime=anchor_regime,
        candidate_regime=candidate_regime,
        progress_current=progress_current,
        progress_required=progress_required,
        last_commit_timestamp_ms=last_commit_timestamp_ms,
        reason_codes=reason_codes,
        debug=None,
    )


class TestBeliefHysteresis(unittest.TestCase):
    def test_tie_breaking_is_stable(self) -> None:
        belief = _belief(
            {
                Regime.CHOP_BALANCED: 0.5,
                Regime.CHOP_STOPHUNT: 0.5,
            }
        )
        candidate = select_candidate(belief, Regime.CHOP_STOPHUNT, allowed_regimes=None)
        self.assertEqual(candidate, Regime.CHOP_BALANCED)

    def test_candidate_flip_flop_decays_progress(self) -> None:
        config = HysteresisConfig(window_updates=3, enter_threshold=0.6, commit_threshold=0.6)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=0,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=3,
        )
        state_a = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.6, Regime.CHOP_BALANCED: 0.4}),
        )
        first = advance_hysteresis(prev, state_a, config)
        self.assertEqual(first.candidate_regime, Regime.SQUEEZE_UP)
        self.assertEqual(first.progress_current, 1)

        state_b = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=200,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.CHOP_BALANCED: 1.0}),
        )
        second = advance_hysteresis(first, state_b, config)
        self.assertIsNone(second.candidate_regime)
        self.assertEqual(second.progress_current, 0)

    def test_lead_gating_blocks_candidate(self) -> None:
        config = HysteresisConfig(
            window_updates=3,
            enter_threshold=0.5,
            commit_threshold=0.5,
            min_lead_over_anchor=0.2,
        )
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=0,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=3,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.55, Regime.CHOP_BALANCED: 0.45}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertIsNone(updated.candidate_regime)
        self.assertIn("GATE_FAIL_MIN_LEAD", updated.reason_codes)

    def test_commit_blocked_when_belief_below_threshold(self) -> None:
        config = HysteresisConfig(window_updates=2, enter_threshold=0.5, commit_threshold=0.8)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=Regime.SQUEEZE_UP,
            progress_current=1,
            progress_required=2,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=200,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.7, Regime.CHOP_BALANCED: 0.3}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertEqual(updated.anchor_regime, Regime.CHOP_BALANCED)
        self.assertEqual(updated.candidate_regime, Regime.SQUEEZE_UP)
        self.assertEqual(updated.progress_current, 2)
        self.assertIn("COMMIT_BLOCKED_THRESHOLD", updated.reason_codes)

    def test_commit_switches_anchor(self) -> None:
        config = HysteresisConfig(window_updates=2, enter_threshold=0.5, commit_threshold=0.6)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=Regime.SQUEEZE_UP,
            progress_current=1,
            progress_required=2,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=200,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.6, Regime.CHOP_BALANCED: 0.4}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertEqual(updated.anchor_regime, Regime.SQUEEZE_UP)
        self.assertIsNone(updated.candidate_regime)
        self.assertEqual(updated.progress_current, 0)
        self.assertEqual(updated.last_commit_timestamp_ms, 200)

    def test_idempotence(self) -> None:
        config = HysteresisConfig(window_updates=2, enter_threshold=0.5, commit_threshold=0.6)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=2,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=200,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.6, Regime.CHOP_BALANCED: 0.4}),
        )
        first = advance_hysteresis(prev, state, config)
        second = advance_hysteresis(prev, state, config)
        self.assertEqual(first, second)

    def test_progress_bounds(self) -> None:
        config = HysteresisConfig(window_updates=3, enter_threshold=0.5, commit_threshold=0.6)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=Regime.SQUEEZE_UP,
            progress_current=5,
            progress_required=3,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=200,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.6, Regime.CHOP_BALANCED: 0.4}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertLessEqual(updated.progress_current, config.window_updates)

    def test_reason_codes_sequence(self) -> None:
        config = HysteresisConfig(window_updates=2, enter_threshold=0.5, commit_threshold=0.6)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=0,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=2,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.6, Regime.CHOP_BALANCED: 0.4}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertIn("CANDIDATE_SELECTED:SQUEEZE_UP", updated.reason_codes)
        self.assertIn("PROGRESS_RESET", updated.reason_codes)

    def test_reason_codes_commit_switch(self) -> None:
        config = HysteresisConfig(window_updates=1, enter_threshold=0.5, commit_threshold=0.5)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=0,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=1,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.SQUEEZE_UP: 0.6, Regime.CHOP_BALANCED: 0.4}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertTrue(
            any(code.startswith("COMMIT_SWITCH:") for code in updated.reason_codes)
        )

    def test_reason_codes_no_candidate(self) -> None:
        config = HysteresisConfig(window_updates=2, enter_threshold=0.5, commit_threshold=0.6)
        prev = _hysteresis_state(
            symbol="TEST",
            engine_timestamp_ms=0,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=2,
        )
        state = _regime_state(
            symbol="TEST",
            engine_timestamp_ms=100,
            anchor_regime=Regime.CHOP_BALANCED,
            belief_by_regime=_belief({Regime.CHOP_BALANCED: 1.0}),
        )
        updated = advance_hysteresis(prev, state, config)
        self.assertIn("CANDIDATE_SAME_AS_ANCHOR", updated.reason_codes)


if __name__ == "__main__":
    unittest.main()
