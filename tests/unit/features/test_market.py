import unittest
from typing import Any, cast

from regime_engine.contracts.snapshots import MISSING, MarketSnapshot
from regime_engine.features.market import (
    acceptance_score,
    atr,
    atr_zscore,
    range_expansion,
    sweep_score,
)


def _make_snapshot(**overrides: Any) -> MarketSnapshot:
    data: dict[str, Any] = dict(
        price=1.0,
        vwap=1.0,
        atr=2.0,
        atr_z=3.0,
        range_expansion=4.0,
        structure_levels={},
        acceptance_score=5.0,
        sweep_score=6.0,
    )
    data.update(overrides)
    return MarketSnapshot(**cast(dict[str, Any], data))


class TestMarketFeatures(unittest.TestCase):
    def test_market_features_pass_through(self) -> None:
        snapshot = _make_snapshot()
        self.assertEqual(atr(snapshot), 2.0)
        self.assertEqual(atr_zscore(snapshot), 3.0)
        self.assertEqual(range_expansion(snapshot), 4.0)
        self.assertEqual(acceptance_score(snapshot), 5.0)
        self.assertEqual(sweep_score(snapshot), 6.0)

    def test_market_features_propagate_missing(self) -> None:
        cases = {
            "atr": (atr, "atr"),
            "atr_z": (atr_zscore, "atr_z"),
            "range_expansion": (range_expansion, "range_expansion"),
            "acceptance_score": (acceptance_score, "acceptance_score"),
            "sweep_score": (sweep_score, "sweep_score"),
        }
        for name, (func, field) in cases.items():
            with self.subTest(name=name):
                snapshot = _make_snapshot(**{field: MISSING})
                self.assertIs(func(snapshot), MISSING)


if __name__ == "__main__":
    unittest.main()
