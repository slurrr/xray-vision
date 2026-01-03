import unittest

from regime_engine.evaluation.metrics import (
    flip_frequency,
    forward_return_distribution,
    regime_expectancy,
    regime_persistence,
    time_in_regime,
)
from regime_engine.evaluation.records import LogRecord, TransitionRecord, record_id_for


def _record(timestamp: int, truth: str, selected: str) -> LogRecord:
    return LogRecord(
        schema_version=1,
        record_id=record_id_for("TEST", timestamp),
        symbol="TEST",
        timestamp=timestamp,
        truth_regime=truth,
        truth_confidence=0.5,
        drivers=["d"],
        invalidations=["i"],
        permissions=["p"],
        selected_regime=selected,
        effective_confidence=0.4,
        transition=TransitionRecord(
            stable_regime=selected,
            candidate_regime=None,
            candidate_count=0,
            transition_active=False,
            flipped=False,
            reset_due_to_gap=False,
        ),
    )


class TestMetrics(unittest.TestCase):
    def test_persistence_flip_frequency_and_time(self) -> None:
        records = [
            _record(0, "CHOP_BALANCED", "CHOP_BALANCED"),
            _record(100, "CHOP_BALANCED", "CHOP_BALANCED"),
            _record(200, "SQUEEZE_UP", "CHOP_BALANCED"),
            _record(300, "SQUEEZE_UP", "SQUEEZE_UP"),
        ]

        persistence = regime_persistence(records, key="truth")
        self.assertEqual(persistence["CHOP_BALANCED"], [2])
        self.assertEqual(persistence["SQUEEZE_UP"], [2])

        flips = flip_frequency(records, key="truth")
        self.assertEqual(flips.flips, 1)
        self.assertAlmostEqual(flips.flip_rate_per_update, 1 / 3)

        time_in = time_in_regime(records, key="truth")
        self.assertEqual(time_in["CHOP_BALANCED"], 200)
        self.assertEqual(time_in["SQUEEZE_UP"], 100)

    def test_forward_return_distribution_and_expectancy(self) -> None:
        records = [
            _record(0, "CHOP_BALANCED", "CHOP_BALANCED"),
            _record(100, "SQUEEZE_UP", "SQUEEZE_UP"),
        ]
        forward_returns = {
            record_id_for("TEST", 0): 0.1,
            record_id_for("TEST", 100): -0.2,
        }

        distribution = forward_return_distribution(records, forward_returns, key="truth")
        self.assertEqual(distribution["CHOP_BALANCED"], [0.1])
        self.assertEqual(distribution["SQUEEZE_UP"], [-0.2])

        expectancy = regime_expectancy(records, forward_returns, key="truth")
        self.assertEqual(expectancy["CHOP_BALANCED"], 0.1)
        self.assertEqual(expectancy["SQUEEZE_UP"], -0.2)


if __name__ == "__main__":
    unittest.main()
