import unittest

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.contracts import EngineRunRecord
from orchestrator.replay import replay_events
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime


def _snapshot_event(symbol: str, timestamp_ms: int) -> RawMarketEvent:
    return RawMarketEvent(
        schema="raw_market_event",
        schema_version="1",
        event_type="SnapshotInputs",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=None,
        recv_ts_ms=1,
        raw_payload=b"{}",
        normalized={"timestamp_ms": timestamp_ms, "market": {"price": 1.0}},
    )


def _engine_runner(snapshot) -> RegimeOutput:
    return RegimeOutput(
        symbol=snapshot.symbol,
        timestamp=snapshot.timestamp,
        regime=Regime.CHOP_BALANCED,
        confidence=0.0,
        drivers=[],
        invalidations=[],
        permissions=[],
    )


class TestReplay(unittest.TestCase):
    def test_replay_is_deterministic(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(_snapshot_event("AAA", 100), ingest_ts_ms=1)
        buffer.append(_snapshot_event("AAA", 200), ingest_ts_ms=2)

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

        first = replay_events(buffer=buffer, run_records=run_records, engine_runner=_engine_runner)
        second = replay_events(buffer=buffer, run_records=run_records, engine_runner=_engine_runner)

        self.assertEqual(
            [event.event_type for event in first.events],
            [event.event_type for event in second.events],
        )
        self.assertEqual(
            [event.run_id for event in first.events],
            [event.run_id for event in second.events],
        )

    def test_replay_emits_failure_on_missing_snapshot(self) -> None:
        buffer = RawInputBuffer(max_records=10)
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
            )
        ]

        result = replay_events(buffer=buffer, run_records=run_records, engine_runner=_engine_runner)
        self.assertEqual(result.events[-1].event_type, "EngineRunFailed")


if __name__ == "__main__":
    unittest.main()
