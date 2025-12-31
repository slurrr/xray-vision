import unittest

from regime_engine.contracts.snapshots import (
    MISSING,
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.snapshot_builder.serialize import dumps_snapshot_jsonl, loads_snapshot_jsonl


class TestSnapshotSerialization(unittest.TestCase):
    def test_snapshot_serialization_roundtrip_is_equality_preserving(self) -> None:
        snapshot = RegimeInputSnapshot(
            symbol="TEST",
            timestamp=180_000,
            market=MarketSnapshot(
                price=1.0,
                vwap=MISSING,
                atr=1.0,
                atr_z=0.0,
                range_expansion=0.0,
                structure_levels={"lvl": {"nested": MISSING}},
                acceptance_score=0.0,
                sweep_score=0.0,
            ),
            derivatives=DerivativesSnapshot(
                open_interest=1.0,
                oi_slope_short=0.0,
                oi_slope_med=0.0,
                oi_accel=0.0,
                funding_rate=0.0,
                funding_slope=0.0,
                funding_z=0.0,
                liquidation_intensity=None,
            ),
            flow=FlowSnapshot(
                cvd=0.0,
                cvd_slope=0.0,
                cvd_efficiency=0.0,
                aggressive_volume_ratio=0.0,
            ),
            context=ContextSnapshot(
                rs_vs_btc=0.0,
                beta_to_btc=0.0,
                alt_breadth=0.0,
                btc_regime=None,
                eth_regime=None,
            ),
        )

        line = dumps_snapshot_jsonl(snapshot)
        restored = loads_snapshot_jsonl(line)
        self.assertEqual(restored, snapshot)


if __name__ == "__main__":
    unittest.main()
