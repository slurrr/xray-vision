import unittest

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.cuts import Cut
from orchestrator.snapshots import build_snapshot, select_snapshot_event
from regime_engine.contracts.snapshots import MISSING, is_missing


def _snapshot_event(symbol: str, timestamp_ms: int, seq: int) -> RawMarketEvent:
    return RawMarketEvent(
        schema="raw_market_event",
        schema_version="1",
        event_type="SnapshotInputs",
        source_id="source",
        symbol=symbol,
        exchange_ts_ms=None,
        recv_ts_ms=seq,
        raw_payload=b"{}",
        normalized={"timestamp_ms": timestamp_ms, "market": {"price": 1.0}},
    )


class TestSnapshots(unittest.TestCase):
    def test_selects_highest_ingest_seq_in_cut(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(_snapshot_event("AAA", 100, 1), ingest_ts_ms=1)
        buffer.append(_snapshot_event("AAA", 100, 2), ingest_ts_ms=2)
        buffer.append(_snapshot_event("AAA", 101, 3), ingest_ts_ms=3)

        cut = Cut(symbol="AAA", cut_start_ingest_seq=1, cut_end_ingest_seq=3, cut_kind="timer")
        selected = select_snapshot_event(buffer=buffer, cut=cut, engine_timestamp_ms=100)

        self.assertIsNotNone(selected)
        self.assertEqual(selected.recv_ts_ms, 2)

    def test_build_snapshot_marks_missing_fields(self) -> None:
        event = _snapshot_event("AAA", 100, 1)
        snapshot = build_snapshot(symbol="AAA", engine_timestamp_ms=100, snapshot_event=event)

        self.assertEqual(snapshot.market.price, 1.0)
        self.assertTrue(is_missing(snapshot.market.vwap))
        self.assertTrue(is_missing(snapshot.derivatives.open_interest))
        self.assertTrue(is_missing(snapshot.flow.cvd))
        self.assertTrue(is_missing(snapshot.context.rs_vs_btc))


if __name__ == "__main__":
    unittest.main()
