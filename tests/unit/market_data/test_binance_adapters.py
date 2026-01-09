import unittest

from market_data.adapters.binance.adapter import (
    BinanceAggTradeAdapter,
    BinanceMarkPriceAdapter,
)
from market_data.adapters.binance.config import (
    BinanceAggTradeConfig,
    BinanceMarkPriceConfig,
)
from market_data.config import BackpressureConfig
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline


class RecordingSink:
    def __init__(self) -> None:
        self.events = []

    def write(self, event, *, block: bool, timeout_ms: int | None) -> None:
        self.events.append(event)


class TestBinanceAdapters(unittest.TestCase):
    def _pipeline(self, sink: RecordingSink) -> IngestionPipeline:
        return IngestionPipeline(
            sink=sink,
            backpressure=BackpressureConfig(policy="block", max_pending=1, max_block_ms=50),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=lambda: 100,
        )

    def test_agg_trade_emits_trade_tick(self) -> None:
        sink = RecordingSink()
        pipeline = self._pipeline(sink)
        adapter = BinanceAggTradeAdapter(
            config=BinanceAggTradeConfig.default(symbol="BTCUSDT"),
            pipeline=pipeline,
        )
        message = (
            '{"e":"aggTrade","E":1,"a":1,'
            '"s":"BTCUSDT","p":"100.0",'
            '"q":"0.5","T":2,"m":true}'
        )
        adapter._handle_message(message)

        self.assertEqual(len(sink.events), 1)
        event = sink.events[0]
        self.assertEqual(event.event_type, "TradeTick")
        self.assertEqual(event.channel, "trades")
        self.assertEqual(event.exchange_ts_ms, 2)
        self.assertEqual(event.normalized["side"], "sell")
        self.assertEqual(event.raw_payload, message)

    def test_mark_price_emits_three_events(self) -> None:
        sink = RecordingSink()
        pipeline = self._pipeline(sink)
        adapter = BinanceMarkPriceAdapter(
            config=BinanceMarkPriceConfig.default(symbol="BTCUSDT"),
            pipeline=pipeline,
        )
        message = (
            '{"e":"markPriceUpdate","E":3,'
            '"s":"BTCUSDT","p":"1.1",'
            '"i":"1.2","r":"0.01"}'
        )
        adapter._handle_message(message)

        self.assertEqual(len(sink.events), 3)
        event_types = {event.event_type for event in sink.events}
        self.assertEqual(event_types, {"MarkPrice", "IndexPrice", "FundingRate"})
        for event in sink.events:
            self.assertEqual(event.channel, "mark_price")
            self.assertEqual(event.raw_payload, message)

    def test_decode_failure_emitted(self) -> None:
        sink = RecordingSink()
        pipeline = self._pipeline(sink)
        adapter = BinanceAggTradeAdapter(
            config=BinanceAggTradeConfig.default(symbol="BTCUSDT"),
            pipeline=pipeline,
        )
        adapter._handle_message("{bad-json}")

        self.assertEqual(len(sink.events), 1)
        event = sink.events[0]
        self.assertEqual(event.event_type, "DecodeFailure")


if __name__ == "__main__":
    unittest.main()
