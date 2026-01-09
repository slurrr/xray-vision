import unittest

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.contracts import EngineRunCompletedPayload, EngineRunRecord
from orchestrator.replay import replay_events
from regime_engine.engine import run


def _trade_event(symbol: str, seq: int) -> RawMarketEvent:
    return RawMarketEvent(
        schema="raw_market_event",
        schema_version="1",
        event_type="TradeTick",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=1,
        recv_ts_ms=seq,
        raw_payload=b"{}",
        normalized={"price": 100.0, "quantity": 1.0, "side": "buy"},
        channel="trades",
    )


def _open_interest_event(symbol: str, seq: int) -> RawMarketEvent:
    return RawMarketEvent(
        schema="raw_market_event",
        schema_version="1",
        event_type="OpenInterest",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=2,
        recv_ts_ms=seq,
        raw_payload=b"{}",
        normalized={"open_interest": 1000.0},
        channel="open_interest",
    )


class TestReplay(unittest.TestCase):
    def test_replay_is_deterministic(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(_trade_event("AAA", 1), ingest_ts_ms=1)
        buffer.append(_open_interest_event("AAA", 2), ingest_ts_ms=2)

        run_records = [
            EngineRunRecord(
                run_id="run-1",
                symbol="AAA",
                engine_timestamp_ms=100,
                engine_mode="truth",
                cut_kind="timer",
                cut_start_ingest_seq=1,
                cut_end_ingest_seq=1,
                planned_ts_ms=90,
                started_ts_ms=91,
                completed_ts_ms=92,
                status="completed",
                attempts=1,
            ),
            EngineRunRecord(
                run_id="run-2",
                symbol="AAA",
                engine_timestamp_ms=200,
                engine_mode="truth",
                cut_kind="timer",
                cut_start_ingest_seq=2,
                cut_end_ingest_seq=2,
                planned_ts_ms=190,
                started_ts_ms=191,
                completed_ts_ms=192,
                status="completed",
                attempts=1,
            ),
        ]

        first = replay_events(buffer=buffer, run_records=run_records, engine_runner=run)
        second = replay_events(buffer=buffer, run_records=run_records, engine_runner=run)

        self.assertEqual(
            [event.event_type for event in first.events],
            [event.event_type for event in second.events],
        )
        self.assertEqual(
            [event.run_id for event in first.events],
            [event.run_id for event in second.events],
        )

    def test_replay_embeds_evidence_without_snapshotinputs(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(_trade_event("AAA", 1), ingest_ts_ms=1)
        buffer.append(_open_interest_event("AAA", 2), ingest_ts_ms=2)
        run_records = [
            EngineRunRecord(
                run_id="run-1",
                symbol="AAA",
                engine_timestamp_ms=180_000,
                engine_mode="truth",
                cut_kind="timer",
                cut_start_ingest_seq=1,
                cut_end_ingest_seq=2,
                planned_ts_ms=90,
                started_ts_ms=91,
                completed_ts_ms=92,
                status="completed",
                attempts=1,
            )
        ]

        result = replay_events(buffer=buffer, run_records=run_records, engine_runner=run)
        completed = result.events[-1]
        self.assertEqual(completed.event_type, "EngineRunCompleted")
        self.assertIsNotNone(completed.payload)
        payload = completed.payload
        self.assertIsInstance(payload, EngineRunCompletedPayload)
        assert isinstance(payload, EngineRunCompletedPayload)
        drivers = payload.regime_output.drivers
        self.assertTrue(any(driver.startswith("composer:") for driver in drivers))
        self.assertEqual(
            completed.counts_by_event_type,
            {"TradeTick": 1, "OpenInterest": 1},
        )


if __name__ == "__main__":
    unittest.main()
