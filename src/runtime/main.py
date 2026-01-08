from __future__ import annotations

import logging
import os
import sys

from market_data.adapters.binance.adapter import BinanceTradeAdapter
from market_data.adapters.binance.config import BinanceTradeAdapterConfig
from market_data.config import BackpressureConfig
from market_data.contracts import RawMarketEvent
from market_data.observability import NullMetrics, Observability, StdlibLogger
from market_data.pipeline import IngestionPipeline
from market_data.sink import RawEventSink
from runtime.bus import EventBus
from runtime.wiring import build_runtime, register_subscriptions

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "xray-vision.log")),
        logging.StreamHandler(sys.stderr),
    ],
)
logging.getLogger("orchestrator").setLevel(logging.DEBUG)
logging.getLogger("market_data").setLevel(logging.DEBUG)
logging.getLogger("consumers").setLevel(logging.DEBUG)
logging.getLogger("runtime").setLevel(logging.DEBUG)


class BusRawEventSink(RawEventSink):
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def write(
        self, event: RawMarketEvent, *, block: bool, timeout_ms: int | None
    ) -> None:
        self._bus.publish(event)


def main() -> None:
    bus = EventBus()
    runtime = build_runtime(bus)
    register_subscriptions(bus, runtime)
    runtime.dashboards.start()
    pipeline = IngestionPipeline(
        sink=BusRawEventSink(bus),
        backpressure=BackpressureConfig(policy="fail", max_pending=10_000),
        observability=Observability(
            logger=StdlibLogger(logging.getLogger("market_data")),
            metrics=NullMetrics(),
        ),
    )
    adapter = BinanceTradeAdapter(
        config=BinanceTradeAdapterConfig.default(),
        pipeline=pipeline,
    )
    adapter.start()
    try:
        adapter.run()
    finally:
        adapter.stop()
        runtime.dashboards.stop()


if __name__ == "__main__":
    main()
