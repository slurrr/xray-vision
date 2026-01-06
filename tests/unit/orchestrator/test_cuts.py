import unittest

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.cuts import CutSelector


def _event(symbol: str) -> RawMarketEvent:
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


class TestCutSelector(unittest.TestCase):
    def test_cut_selects_first_symbol_seq(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(_event("AAA"), ingest_ts_ms=1)
        buffer.append(_event("BBB"), ingest_ts_ms=2)
        buffer.append(_event("AAA"), ingest_ts_ms=3)

        selector = CutSelector()
        cut = selector.next_cut(buffer=buffer, symbol="AAA", cut_end_ingest_seq=3, cut_kind="timer")

        self.assertEqual(cut.cut_start_ingest_seq, 1)
        self.assertEqual(cut.cut_end_ingest_seq, 3)

    def test_cut_advances_from_last_end(self) -> None:
        buffer = RawInputBuffer(max_records=10)
        buffer.append(_event("AAA"), ingest_ts_ms=1)
        buffer.append(_event("AAA"), ingest_ts_ms=2)
        buffer.append(_event("AAA"), ingest_ts_ms=3)

        selector = CutSelector()
        selector.next_cut(buffer=buffer, symbol="AAA", cut_end_ingest_seq=2, cut_kind="timer")
        cut = selector.next_cut(buffer=buffer, symbol="AAA", cut_end_ingest_seq=3, cut_kind="timer")

        self.assertEqual(cut.cut_start_ingest_seq, 3)
        self.assertEqual(cut.cut_end_ingest_seq, 3)


if __name__ == "__main__":
    unittest.main()
