import unittest

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.evaluation.logging import build_log_record, log_path
from regime_engine.hysteresis.state import SCHEMA_NAME, SCHEMA_VERSION, HysteresisState


class TestLogging(unittest.TestCase):
    def test_build_log_record(self) -> None:
        output = RegimeOutput(
            symbol="TEST",
            timestamp=180_000,
            regime=Regime.CHOP_BALANCED,
            confidence=0.8,
            drivers=["driver"],
            invalidations=["invalid"],
            permissions=["perm"],
        )
        hysteresis_state = HysteresisState(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            symbol="TEST",
            engine_timestamp_ms=180_000,
            anchor_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            progress_current=0,
            progress_required=3,
            last_commit_timestamp_ms=None,
            reason_codes=(),
            debug=None,
        )

        record = build_log_record(output, hysteresis_state)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.schema_version, 1)
        self.assertEqual(record.record_id, "TEST:180000")
        self.assertEqual(record.truth_regime, "CHOP_BALANCED")
        self.assertEqual(record.selected_regime, "CHOP_BALANCED")

    def test_log_path_partitions_by_day(self) -> None:
        path = log_path(base_dir="logs/regime", timestamp=0)
        self.assertEqual(path, "logs/regime/1970-01-01.jsonl")


if __name__ == "__main__":
    unittest.main()
