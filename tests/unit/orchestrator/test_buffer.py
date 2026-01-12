import unittest

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import BufferFullError, RawInputBuffer


class TestRawInputBuffer(unittest.TestCase):
    def _event(self, symbol: str) -> RawMarketEvent:
        return RawMarketEvent(
            schema="raw_market_event",
            schema_version="1",
            event_type="TradeTick",
            source_id="source",
            symbol=symbol,
            exchange_ts_ms=None,
            recv_ts_ms=1,
            raw_payload=b"{}",
            normalized={"price": 1.0, "quantity": 1.0, "side": None},
        )

    def test_append_assigns_strictly_increasing_seq(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        first = buffer.append(self._event("AAA"), ingest_ts_ms=10)
        second = buffer.append(self._event("AAA"), ingest_ts_ms=20)

        self.assertEqual(first.ingest_seq, 1)
        self.assertEqual(second.ingest_seq, 2)
        self.assertEqual(buffer.last_ingest_seq(), 2)

    def test_append_preserves_event_object(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        event = self._event("AAA")
        record = buffer.append(event, ingest_ts_ms=10)
        self.assertIs(record.event, event)

    def test_capacity_enforced(self) -> None:
        buffer = RawInputBuffer(max_records=1)
        buffer.append(self._event("AAA"), ingest_ts_ms=10)
        with self.assertRaises(BufferFullError):
            buffer.append(self._event("BBB"), ingest_ts_ms=20)

    def test_range_by_symbol_filters(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(self._event("AAA"), ingest_ts_ms=10)
        buffer.append(self._event("BBB"), ingest_ts_ms=20)
        buffer.append(self._event("AAA"), ingest_ts_ms=30)

        records = buffer.range_by_symbol(symbol="AAA", start_seq=1, end_seq=3)
        self.assertEqual([record.event.symbol for record in records], ["AAA", "AAA"])

    def test_drop_through_removes_consumed_records(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(self._event("AAA"), ingest_ts_ms=10)
        buffer.append(self._event("BBB"), ingest_ts_ms=20)
        buffer.append(self._event("AAA"), ingest_ts_ms=30)

        dropped = buffer.drop_through(end_seq=2)

        self.assertEqual(dropped, 2)
        remaining = buffer.all_records()
        self.assertEqual([record.ingest_seq for record in remaining], [3])


if __name__ == "__main__":
    unittest.main()
