import unittest

from regime_engine.explainability.drivers import drivers_from_contributors


class TestDrivers(unittest.TestCase):
    def test_preserves_order_and_dedupes(self) -> None:
        contributors = [
            "market.range_expansion",
            "flow.cvd_slope",
            "market.range_expansion",
            "flow.cvd_slope",
        ]
        drivers = drivers_from_contributors(contributors)
        self.assertEqual(drivers, ["Market range expansion", "Flow CVD slope"])

    def test_unknown_contributor_is_verbatim(self) -> None:
        drivers = drivers_from_contributors(["market.atr_zscore", "mystery.field"])
        self.assertEqual(drivers, ["Market ATR z-score", "mystery.field"])


if __name__ == "__main__":
    unittest.main()
