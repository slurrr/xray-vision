import unittest

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.evaluation.logging import build_log_record, log_path
from regime_engine.hysteresis.decision import HysteresisDecision, HysteresisTransition


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
        transition = HysteresisTransition(
            stable_regime=Regime.CHOP_BALANCED,
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=False,
        )
        decision = HysteresisDecision(
            selected_output=output,
            effective_confidence=0.7,
            transition=transition,
        )

        record = build_log_record(output, decision)
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
