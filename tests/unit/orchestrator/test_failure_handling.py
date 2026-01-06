import unittest

from orchestrator.failure_handling import (
    BackpressureState,
    BufferAppendFailure,
    FailureHandler,
    IngestionFailure,
    PublishFailure,
)
from orchestrator.lifecycle import Lifecycle, OrchestratorState
from orchestrator.retry import Retrier, RetrySchedule


class TestFailureHandling(unittest.TestCase):
    def test_buffer_append_failure_degrades(self) -> None:
        lifecycle = Lifecycle()
        backpressure = BackpressureState()
        handler = FailureHandler(lifecycle=lifecycle, backpressure=backpressure)

        retrier = Retrier(RetrySchedule(min_delay_ms=1, max_delay_ms=1, max_attempts=1))

        with self.assertRaises(BufferAppendFailure):
            handler.handle_buffer_append(
                lambda: (_ for _ in ()).throw(RuntimeError("fail")), retrier
            )

        self.assertEqual(lifecycle.state, OrchestratorState.DEGRADED)
        self.assertTrue(backpressure.ingestion_paused)

    def test_publish_failure_pauses_scheduling(self) -> None:
        lifecycle = Lifecycle()
        backpressure = BackpressureState()
        handler = FailureHandler(lifecycle=lifecycle, backpressure=backpressure)

        retrier = Retrier(RetrySchedule(min_delay_ms=1, max_delay_ms=1, max_attempts=1))

        with self.assertRaises(PublishFailure):
            handler.handle_publish(lambda: (_ for _ in ()).throw(RuntimeError("fail")), retrier)

        self.assertTrue(backpressure.scheduling_paused)

    def test_ingestion_failure_raises(self) -> None:
        lifecycle = Lifecycle()
        backpressure = BackpressureState()
        handler = FailureHandler(lifecycle=lifecycle, backpressure=backpressure)

        retrier = Retrier(RetrySchedule(min_delay_ms=1, max_delay_ms=1, max_attempts=1))

        with self.assertRaises(IngestionFailure):
            handler.handle_ingestion(lambda: (_ for _ in ()).throw(RuntimeError("fail")), retrier)


if __name__ == "__main__":
    unittest.main()
