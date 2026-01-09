import unittest

from market_data.adapters.binance.decoder import (
    DecodeError,
    decode_agg_trade,
    decode_book_ticker,
    decode_depth,
    decode_force_order,
    decode_kline,
    decode_mark_price,
    decode_open_interest,
)


class TestBinanceDecoder(unittest.TestCase):
    def test_decode_agg_trade(self) -> None:
        payload = {
            "T": 1,
            "p": "100.5",
            "q": "0.25",
            "m": False,
            "a": 123,
        }
        event = decode_agg_trade(payload)
        self.assertEqual(event.event_type, "TradeTick")
        self.assertEqual(event.exchange_ts_ms, 1)
        self.assertEqual(event.normalized["price"], 100.5)
        self.assertEqual(event.normalized["quantity"], 0.25)
        self.assertEqual(event.normalized["side"], "buy")
        self.assertEqual(event.source_event_id, "123")

    def test_decode_kline(self) -> None:
        payload = {
            "E": 2,
            "k": {
                "T": 3,
                "i": "3m",
                "o": "1.0",
                "h": "2.0",
                "l": "0.5",
                "c": "1.5",
                "v": "10.0",
                "x": True,
            },
        }
        event = decode_kline(payload)
        self.assertEqual(event.event_type, "Candle")
        self.assertEqual(event.exchange_ts_ms, 3)
        self.assertEqual(event.normalized["interval_ms"], 180000)
        self.assertEqual(event.normalized["is_final"], True)

    def test_decode_book_ticker(self) -> None:
        payload = {"b": "1.0", "B": "2.0", "a": "1.1", "A": "3.0", "E": 4}
        event = decode_book_ticker(payload)
        self.assertEqual(event.event_type, "BookTop")
        self.assertEqual(event.exchange_ts_ms, 4)
        self.assertEqual(event.normalized["best_bid_price"], 1.0)

    def test_decode_depth(self) -> None:
        payload = {"b": [["1.0", "2.0"]], "a": [["3.0", "4.0"]], "u": 9}
        event = decode_depth(payload)
        self.assertEqual(event.event_type, "BookDelta")
        self.assertEqual(event.source_seq, 9)
        self.assertEqual(event.normalized["bids"], [[1.0, 2.0]])

    def test_decode_mark_price(self) -> None:
        payload = {"p": "1.1", "i": "1.2", "r": "0.01", "E": 5}
        result = decode_mark_price(payload)
        self.assertEqual(len(result.events), 3)
        event_types = {event.event_type for event in result.events}
        self.assertEqual(
            event_types, {"MarkPrice", "IndexPrice", "FundingRate"}
        )
        self.assertEqual(result.errors, ())

    def test_decode_force_order(self) -> None:
        payload = {"o": {"p": "1.0", "q": "2.0", "S": "SELL", "T": 6}}
        event = decode_force_order(payload)
        self.assertEqual(event.event_type, "LiquidationPrint")
        self.assertEqual(event.exchange_ts_ms, 6)
        self.assertEqual(event.normalized["side"], "sell")

    def test_decode_open_interest(self) -> None:
        payload = {"openInterest": "123.5", "time": 7}
        event = decode_open_interest(payload)
        self.assertEqual(event.event_type, "OpenInterest")
        self.assertEqual(event.exchange_ts_ms, 7)
        self.assertEqual(event.normalized["open_interest"], 123.5)

    def test_decode_missing_required_field(self) -> None:
        with self.assertRaises(DecodeError):
            decode_agg_trade({"T": 1, "q": "1.0"})


if __name__ == "__main__":
    unittest.main()
