from __future__ import annotations

import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis import HysteresisStore, process_state
from regime_engine.hysteresis.rules import advance_hysteresis
from regime_engine.hysteresis.state import HysteresisConfig, HysteresisState
from regime_engine.state.state import SCHEMA_NAME, SCHEMA_VERSION, RegimeState


def _make_regime_state(
    *, engine_timestamp_ms: int, anchor_regime: Regime
) -> RegimeState:
    belief_by_regime = {
        Regime.CHOP_BALANCED: 0.7,
        Regime.TREND_BUILD_UP: 0.2,
    }
    return RegimeState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol="TEST",
        engine_timestamp_ms=engine_timestamp_ms,
        belief_by_regime=belief_by_regime,
        anchor_regime=anchor_regime,
    )


def _build_prev_state(config: HysteresisConfig, *, engine_timestamp_ms: int) -> HysteresisState:
    prev_regime_state = _make_regime_state(
        engine_timestamp_ms=engine_timestamp_ms, anchor_regime=Regime.CHOP_BALANCED
    )
    return advance_hysteresis(None, prev_regime_state, config)


class TestHysteresisTimeGapReset(unittest.TestCase):
    def test_gap_at_threshold_does_not_reset(self) -> None:
        config = HysteresisConfig(
            window_updates=3,
            enter_threshold=0.1,
            commit_threshold=2.0,
            reset_max_gap_ms=720_000,
        )
        prev_state = _build_prev_state(config, engine_timestamp_ms=1_000)
        store = HysteresisStore(states={"TEST": prev_state})
        current_state = _make_regime_state(
            engine_timestamp_ms=1_000 + 720_000, anchor_regime=Regime.TREND_BUILD_UP
        )

        result = process_state(current_state, store=store, config=config)

        expected = advance_hysteresis(prev_state, current_state, config)
        self.assertEqual(result, expected)

    def test_gap_above_threshold_resets_state(self) -> None:
        config = HysteresisConfig(
            window_updates=3,
            enter_threshold=0.1,
            commit_threshold=2.0,
            reset_max_gap_ms=720_000,
        )
        prev_state = _build_prev_state(config, engine_timestamp_ms=1_000)
        store = HysteresisStore(states={"TEST": prev_state})
        current_state = _make_regime_state(
            engine_timestamp_ms=1_000 + 720_001, anchor_regime=Regime.TREND_BUILD_UP
        )

        result = process_state(current_state, store=store, config=config)

        expected = advance_hysteresis(None, current_state, config)
        self.assertEqual(result, expected)
        self.assertEqual(store.state_for("TEST"), result)


if __name__ == "__main__":
    unittest.main()
