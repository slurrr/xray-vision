import unittest
from typing import Any, cast

from regime_engine.contracts.snapshots import MISSING, ContextSnapshot
from regime_engine.features.context import alt_breadth, beta_to_btc, rs_vs_btc


def _make_snapshot(**overrides: Any) -> ContextSnapshot:
    data: dict[str, Any] = dict(
        rs_vs_btc=1.0,
        beta_to_btc=2.0,
        alt_breadth=3.0,
        btc_regime=None,
        eth_regime=None,
    )
    data.update(overrides)
    return ContextSnapshot(**cast(dict[str, Any], data))


class TestContextFeatures(unittest.TestCase):
    def test_context_features_pass_through(self) -> None:
        snapshot = _make_snapshot()
        self.assertEqual(rs_vs_btc(snapshot), 1.0)
        self.assertEqual(beta_to_btc(snapshot), 2.0)
        self.assertEqual(alt_breadth(snapshot), 3.0)

    def test_context_features_propagate_missing(self) -> None:
        cases = {
            "rs_vs_btc": (rs_vs_btc, "rs_vs_btc"),
            "beta_to_btc": (beta_to_btc, "beta_to_btc"),
            "alt_breadth": (alt_breadth, "alt_breadth"),
        }
        for name, (func, field) in cases.items():
            with self.subTest(name=name):
                snapshot = _make_snapshot(**{field: MISSING})
                self.assertIs(func(snapshot), MISSING)


if __name__ == "__main__":
    unittest.main()
