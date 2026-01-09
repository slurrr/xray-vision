from __future__ import annotations

import logging
import os
import sys

from composer.observability import Observability as ComposerObservability
from composer.observability import StdlibLogger as ComposerStdlibLogger
from composer.observability import set_observability as set_composer_observability
from market_data.adapters.binance.adapter import BinanceTradeAdapter
from market_data.adapters.binance.config import BinanceTradeAdapterConfig
from market_data.config import BackpressureConfig
from market_data.contracts import RawMarketEvent
from market_data.observability import NullMetrics, Observability, StdlibLogger
from market_data.pipeline import IngestionPipeline
from market_data.sink import RawEventSink
from regime_engine.observability import Observability as RegimeObservability
from regime_engine.observability import StdlibLogger as RegimeStdlibLogger
from regime_engine.observability import set_observability as set_regime_observability
from runtime.bus import EventBus
from runtime.wiring import build_runtime, register_subscriptions

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "xray-vision.log")),
        logging.StreamHandler(sys.stderr),
    ],
)
logging.getLogger("orchestrator").setLevel(logging.DEBUG)
logging.getLogger("market_data").setLevel(logging.WARNING)
logging.getLogger("consumers").setLevel(logging.DEBUG)
logging.getLogger("runtime").setLevel(logging.DEBUG)
logging.getLogger("composer").setLevel(logging.INFO)
logging.getLogger("regime_engine").setLevel(logging.INFO)


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
    set_composer_observability(
        ComposerObservability(
            logger=ComposerStdlibLogger(logging.getLogger("composer")),
        )
    )
    set_regime_observability(
        RegimeObservability(
            logger=RegimeStdlibLogger(logging.getLogger("regime_engine")),
        )
    )
    runtime.dashboards.start()
    runtime.dashboards.render_once()
    logging.getLogger("runtime").info("runtime_started")
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
        observability=Observability(
            logger=StdlibLogger(logging.getLogger("market_data")),
            metrics=NullMetrics(),
        ),
    )
    logging.getLogger("runtime").info("market_data_adapter_initialized")
    adapter.start()
    try:
        adapter.run()
    finally:
        adapter.stop()
        runtime.dashboards.stop()


if __name__ == "__main__":
    main()
