import unittest

from regime_engine.evaluation.records import LogRecord, TransitionRecord, record_id_for
from regime_engine.evaluation.replay import group_by_symbol


def _record(symbol: str, timestamp: int) -> LogRecord:
    return LogRecord(
        schema_version=1,
        record_id=record_id_for(symbol, timestamp),
        symbol=symbol,
        timestamp=timestamp,
        truth_regime="CHOP_BALANCED",
        truth_confidence=0.5,
        drivers=["d"],
        invalidations=["i"],
        permissions=["p"],
        selected_regime="CHOP_BALANCED",
        effective_confidence=0.4,
        transition=TransitionRecord(
            stable_regime="CHOP_BALANCED",
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=False,
        ),
    )


class TestReplay(unittest.TestCase):
    def test_group_by_symbol_sorts_and_dedupes(self) -> None:
        records = [
            _record("TEST", 300),
            _record("TEST", 100),
            _record("TEST", 100),
            _record("TEST", 200),
        ]

        grouped = group_by_symbol(records)
        self.assertEqual([rec.timestamp for rec in grouped["TEST"]], [100, 200, 300])


if __name__ == "__main__":
    unittest.main()
