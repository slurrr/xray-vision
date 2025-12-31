import unittest

from regime_engine.contracts.snapshots import FlowSnapshot, MISSING
from regime_engine.features.flow import aggressive_volume_ratio, cvd_efficiency, cvd_slope


def _make_snapshot(**overrides: object) -> FlowSnapshot:
    data = dict(
        cvd=1.0,
        cvd_slope=2.0,
        cvd_efficiency=3.0,
        aggressive_volume_ratio=4.0,
    )
    data.update(overrides)
    return FlowSnapshot(**data)


class TestFlowFeatures(unittest.TestCase):
    def test_flow_features_pass_through(self) -> None:
        snapshot = _make_snapshot()
        self.assertEqual(cvd_slope(snapshot), 2.0)
        self.assertEqual(cvd_efficiency(snapshot), 3.0)
        self.assertEqual(aggressive_volume_ratio(snapshot), 4.0)

    def test_flow_features_propagate_missing(self) -> None:
        cases = {
            "cvd_slope": (cvd_slope, "cvd_slope"),
            "cvd_efficiency": (cvd_efficiency, "cvd_efficiency"),
            "aggressive_volume_ratio": (aggressive_volume_ratio, "aggressive_volume_ratio"),
        }
        for name, (func, field) in cases.items():
            with self.subTest(name=name):
                snapshot = _make_snapshot(**{field: MISSING})
                self.assertIs(func(snapshot), MISSING)


if __name__ == "__main__":
    unittest.main()
