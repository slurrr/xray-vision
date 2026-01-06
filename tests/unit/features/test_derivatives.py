import unittest
from typing import Any, cast

from regime_engine.contracts.snapshots import MISSING, DerivativesSnapshot
from regime_engine.features.derivatives import (
    funding_level,
    funding_slope,
    funding_zscore,
    oi_acceleration,
    oi_slope_med,
    oi_slope_short,
)


def _make_snapshot(**overrides: Any) -> DerivativesSnapshot:
    data: dict[str, Any] = dict(
        open_interest=1.0,
        oi_slope_short=2.0,
        oi_slope_med=3.0,
        oi_accel=4.0,
        funding_rate=5.0,
        funding_slope=6.0,
        funding_z=7.0,
        liquidation_intensity=None,
    )
    data.update(overrides)
    return DerivativesSnapshot(**cast(dict[str, Any], data))


class TestDerivativesFeatures(unittest.TestCase):
    def test_derivatives_features_pass_through(self) -> None:
        snapshot = _make_snapshot()
        self.assertEqual(oi_slope_short(snapshot), 2.0)
        self.assertEqual(oi_slope_med(snapshot), 3.0)
        self.assertEqual(oi_acceleration(snapshot), 4.0)
        self.assertEqual(funding_level(snapshot), 5.0)
        self.assertEqual(funding_slope(snapshot), 6.0)
        self.assertEqual(funding_zscore(snapshot), 7.0)

    def test_derivatives_features_propagate_missing(self) -> None:
        cases = {
            "oi_slope_short": (oi_slope_short, "oi_slope_short"),
            "oi_slope_med": (oi_slope_med, "oi_slope_med"),
            "oi_accel": (oi_acceleration, "oi_accel"),
            "funding_rate": (funding_level, "funding_rate"),
            "funding_slope": (funding_slope, "funding_slope"),
            "funding_z": (funding_zscore, "funding_z"),
        }
        for name, (func, field) in cases.items():
            with self.subTest(name=name):
                snapshot = _make_snapshot(**{field: MISSING})
                self.assertIs(func(snapshot), MISSING)


if __name__ == "__main__":
    unittest.main()
