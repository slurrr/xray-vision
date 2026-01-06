import unittest

from market_data.adapter import AdapterState, AdapterSupervisor, StreamKey
from market_data.config import RetryPolicy


class TestAdapterSupervisor(unittest.TestCase):
    def test_retry_schedule_is_deterministic(self) -> None:
        supervisor = AdapterSupervisor(
            stream_key=StreamKey(source_id="test", channel="trades"),
            retry_policy=RetryPolicy(min_delay_ms=100, max_delay_ms=1000, max_attempts=4),
        )

        self.assertEqual(supervisor.retry_schedule.delays(), (100, 200, 400, 800))

    def test_supervisor_tracks_failures_and_delays(self) -> None:
        supervisor = AdapterSupervisor(
            stream_key=StreamKey(source_id="test", channel="trades"),
            retry_policy=RetryPolicy(min_delay_ms=100, max_delay_ms=1000, max_attempts=2),
        )

        self.assertIsNone(supervisor.next_retry_delay_ms())
        supervisor.record_failure(RuntimeError("fail"))
        self.assertEqual(supervisor.status.state, AdapterState.FAILED)
        self.assertEqual(supervisor.next_retry_delay_ms(), 100)
        supervisor.record_failure(RuntimeError("fail"))
        self.assertEqual(supervisor.next_retry_delay_ms(), 200)


if __name__ == "__main__":
    unittest.main()
