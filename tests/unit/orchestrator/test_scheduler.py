import unittest

from orchestrator.config import SchedulerConfig
from orchestrator.scheduler import Scheduler
from orchestrator.sequencing import SymbolSequencer


class TestScheduler(unittest.TestCase):
    def test_timer_scheduler_is_deterministic(self) -> None:
        scheduler = Scheduler(SchedulerConfig(mode="timer", timer_interval_ms=1000))
        first = scheduler.next_tick_ms(now_ms=100)
        second = scheduler.next_tick_ms(now_ms=200)
        third = scheduler.next_tick_ms(now_ms=300)

        self.assertEqual(first, 100)
        self.assertEqual(second, 1100)
        self.assertEqual(third, 2100)

    def test_boundary_scheduler_aligns_to_interval(self) -> None:
        scheduler = Scheduler(
            SchedulerConfig(mode="boundary", boundary_interval_ms=3000, boundary_delay_ms=500)
        )
        first = scheduler.next_tick_ms(now_ms=1000)
        second = scheduler.next_tick_ms(now_ms=2000)

        self.assertEqual(first, 3500)
        self.assertEqual(second, 6500)


class TestSymbolSequencer(unittest.TestCase):
    def test_monotonic_enforced(self) -> None:
        sequencer = SymbolSequencer()
        sequencer.ensure_next(symbol="TEST", engine_timestamp_ms=100)
        sequencer.ensure_next(symbol="TEST", engine_timestamp_ms=100)
        with self.assertRaises(ValueError):
            sequencer.ensure_next(symbol="TEST", engine_timestamp_ms=99)


if __name__ == "__main__":
    unittest.main()
