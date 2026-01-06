import unittest

from orchestrator.publisher import OrchestratorEventPublisher, build_engine_run_started
from orchestrator.sequencing import SymbolSequencer


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event) -> None:
        self.events.append(event)


class TestPublisher(unittest.TestCase):
    def test_per_symbol_ordering(self) -> None:
        sink = RecordingSink()
        publisher = OrchestratorEventPublisher(sink=sink, sequencer=SymbolSequencer())

        event1 = build_engine_run_started(
            run_id="run-1",
            symbol="TEST",
            engine_timestamp_ms=100,
            cut_start_ingest_seq=1,
            cut_end_ingest_seq=2,
            cut_kind="timer",
            engine_mode="truth",
        )
        event2 = build_engine_run_started(
            run_id="run-2",
            symbol="TEST",
            engine_timestamp_ms=90,
            cut_start_ingest_seq=3,
            cut_end_ingest_seq=4,
            cut_kind="timer",
            engine_mode="truth",
        )

        publisher.publish(event1)
        with self.assertRaises(ValueError):
            publisher.publish(event2)


if __name__ == "__main__":
    unittest.main()
