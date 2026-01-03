import unittest

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis import HysteresisConfig, HysteresisError, apply_hysteresis
from regime_engine.hysteresis.state import HysteresisState


def _output(regime: Regime, timestamp: int, confidence: float = 0.8) -> RegimeOutput:
    return RegimeOutput(
        symbol="TEST",
        timestamp=timestamp,
        regime=regime,
        confidence=confidence,
        drivers=["driver"],
        invalidations=["invalid"],
        permissions=["perm"],
    )


class TestHysteresisRules(unittest.TestCase):
    def test_initial_output_sets_stable(self) -> None:
        config = HysteresisConfig()
        state = HysteresisState()
        output = _output(Regime.CHOP_BALANCED, 180_000, 0.9)

        decision, next_state = apply_hysteresis(output, state=state, config=config)

        self.assertEqual(decision.selected_output, output)
        self.assertEqual(decision.effective_confidence, 0.9)
        self.assertFalse(decision.transition.transition_active)
        self.assertEqual(decision.transition.stable_regime, Regime.CHOP_BALANCED)
        self.assertEqual(decision.transition.candidate_count, 0)
        self.assertEqual(next_state.stable_output, output)

    def test_rejects_non_increasing_timestamp(self) -> None:
        config = HysteresisConfig()
        state = HysteresisState(last_timestamp=180_000)
        output = _output(Regime.CHOP_BALANCED, 180_000, 0.9)

        with self.assertRaises(HysteresisError):
            apply_hysteresis(output, state=state, config=config)

    def test_gap_resets_state(self) -> None:
        config = HysteresisConfig()
        state = HysteresisState(
            stable_output=_output(Regime.CHOP_BALANCED, 180_000, 0.9),
            candidate_regime=Regime.SQUEEZE_UP,
            candidate_count=2,
            last_timestamp=180_000,
        )
        output = _output(Regime.SQUEEZE_UP, 360_001, 0.7)

        decision, next_state = apply_hysteresis(output, state=state, config=config)

        self.assertEqual(decision.selected_output, output)
        self.assertTrue(decision.transition.reset_due_to_gap)
        self.assertFalse(decision.transition.transition_active)
        self.assertEqual(next_state.stable_output, output)
        self.assertEqual(next_state.candidate_count, 0)

    def test_transition_holds_stable_with_decay(self) -> None:
        config = HysteresisConfig()
        stable = _output(Regime.CHOP_BALANCED, 180_000, 0.9)
        state = HysteresisState(
            stable_output=stable,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=180_000,
        )

        output = _output(Regime.SQUEEZE_UP, 360_000, 0.5)
        decision, next_state = apply_hysteresis(output, state=state, config=config)

        self.assertEqual(decision.selected_output, stable)
        self.assertTrue(decision.transition.transition_active)
        self.assertEqual(decision.transition.candidate_count, 1)
        self.assertAlmostEqual(decision.effective_confidence, 0.9 * 0.85)
        self.assertEqual(next_state.candidate_regime, Regime.SQUEEZE_UP)

        output = _output(Regime.SQUEEZE_UP, 540_000, 0.5)
        decision, next_state = apply_hysteresis(output, state=next_state, config=config)
        self.assertEqual(decision.selected_output, stable)
        self.assertEqual(decision.transition.candidate_count, 2)
        self.assertAlmostEqual(decision.effective_confidence, 0.9 * 0.85**2)

    def test_flip_accepts_after_persistence_and_confidence(self) -> None:
        config = HysteresisConfig()
        stable = _output(Regime.CHOP_BALANCED, 180_000, 0.9)
        state = HysteresisState(
            stable_output=stable,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=180_000,
        )

        output = _output(Regime.SQUEEZE_UP, 360_000, 0.7)
        _, state = apply_hysteresis(output, state=state, config=config)
        output = _output(Regime.SQUEEZE_UP, 540_000, 0.7)
        _, state = apply_hysteresis(output, state=state, config=config)
        output = _output(Regime.SQUEEZE_UP, 720_000, 0.7)

        decision, next_state = apply_hysteresis(output, state=state, config=config)

        self.assertEqual(decision.selected_output, output)
        self.assertTrue(decision.transition.flipped)
        self.assertFalse(decision.transition.transition_active)
        self.assertEqual(decision.effective_confidence, 0.7)
        self.assertEqual(next_state.stable_output, output)
        self.assertEqual(next_state.candidate_count, 0)

    def test_reversion_resets_candidate(self) -> None:
        config = HysteresisConfig()
        stable = _output(Regime.CHOP_BALANCED, 180_000, 0.9)
        state = HysteresisState(
            stable_output=stable,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=180_000,
        )

        output = _output(Regime.SQUEEZE_UP, 360_000, 0.5)
        _, state = apply_hysteresis(output, state=state, config=config)

        output = _output(Regime.CHOP_BALANCED, 540_000, 0.9)
        decision, next_state = apply_hysteresis(output, state=state, config=config)

        self.assertEqual(decision.selected_output, output)
        self.assertFalse(decision.transition.transition_active)
        self.assertEqual(next_state.candidate_count, 0)
        self.assertIsNone(next_state.candidate_regime)

    def test_confidence_decay_floor(self) -> None:
        config = HysteresisConfig(min_confidence_floor=0.2)
        stable = _output(Regime.CHOP_BALANCED, 180_000, 0.2)
        state = HysteresisState(
            stable_output=stable,
            candidate_regime=None,
            candidate_count=0,
            last_timestamp=180_000,
        )

        output = _output(Regime.SQUEEZE_UP, 360_000, 0.5)
        decision, _ = apply_hysteresis(output, state=state, config=config)

        self.assertEqual(decision.effective_confidence, 0.2)


if __name__ == "__main__":
    unittest.main()
