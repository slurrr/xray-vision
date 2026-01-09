from __future__ import annotations

import threading
import time

from market_data.adapters.binance.adapter import (
    BinanceAggTradeAdapter,
    BinanceBookTickerAdapter,
    BinanceDepthAdapter,
    BinanceForceOrderAdapter,
    BinanceKlineAdapter,
    BinanceMarkPriceAdapter,
    BinanceOpenInterestPoller,
)
from market_data.adapters.binance.config import (
    BinanceAggTradeConfig,
    BinanceBookTickerConfig,
    BinanceDepthConfig,
    BinanceForceOrderConfig,
    BinanceKlineConfig,
    BinanceMarkPriceConfig,
    BinanceOpenInterestConfig,
)
from market_data.config import BackpressureConfig
from market_data.contracts import RawMarketEvent
from market_data.observability import NullMetrics, Observability
from market_data.pipeline import IngestionPipeline
from market_data.sink import RawEventSink
from runtime.bus import EventBus
from runtime.observability import bootstrap_observability
from runtime.wiring import build_runtime, register_subscriptions

# Configuration will go in config files later
LOG_DIR = "logs"

BINANCE_SYMBOL = "BTCUSDT"
ENABLE_OPTIONAL_BINANCE_CHANNELS = False


class BusRawEventSink(RawEventSink):
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def write(
        self, event: RawMarketEvent, *, block: bool, timeout_ms: int | None
    ) -> None:
        self._bus.publish(event)


def main() -> None:
    observability = bootstrap_observability(log_dir=LOG_DIR)
    bus = EventBus()
    runtime = build_runtime(bus)
    register_subscriptions(bus, runtime)
    runtime.orchestrator.start()
    runtime.dashboards.start()
    runtime.dashboards.render_once()
    observability.runtime.log_runtime_started()
    pipeline = IngestionPipeline(
        sink=BusRawEventSink(bus),
        backpressure=BackpressureConfig(policy="fail", max_pending=10_000),
        observability=Observability(
            logger=observability.market_data.logger,
            metrics=NullMetrics(),
        ),
    )
    adapters = [
        BinanceAggTradeAdapter(
            config=BinanceAggTradeConfig.default(symbol=BINANCE_SYMBOL),
            pipeline=pipeline,
            observability=observability.market_data,
        ),
        BinanceKlineAdapter(
            config=BinanceKlineConfig.default(symbol=BINANCE_SYMBOL),
            pipeline=pipeline,
            observability=observability.market_data,
        ),
        BinanceOpenInterestPoller(
            config=BinanceOpenInterestConfig.default(symbol=BINANCE_SYMBOL),
            pipeline=pipeline,
            observability=observability.market_data,
        ),
    ]
    if ENABLE_OPTIONAL_BINANCE_CHANNELS:
        adapters.extend(
            [
                BinanceBookTickerAdapter(
                    config=BinanceBookTickerConfig.default(symbol=BINANCE_SYMBOL),
                    pipeline=pipeline,
                    observability=observability.market_data,
                ),
                BinanceDepthAdapter(
                    config=BinanceDepthConfig.default(symbol=BINANCE_SYMBOL),
                    pipeline=pipeline,
                    observability=observability.market_data,
                ),
                BinanceMarkPriceAdapter(
                    config=BinanceMarkPriceConfig.default(symbol=BINANCE_SYMBOL),
                    pipeline=pipeline,
                    observability=observability.market_data,
                ),
                BinanceForceOrderAdapter(
                    config=BinanceForceOrderConfig.default(symbol=BINANCE_SYMBOL),
                    pipeline=pipeline,
                    observability=observability.market_data,
                ),
            ]
        )
    observability.runtime.log_market_data_adapters_initialized(
        symbol=BINANCE_SYMBOL,
        adapter_count=len(adapters),
        optional_enabled=ENABLE_OPTIONAL_BINANCE_CHANNELS,
    )
    for adapter in adapters:
        adapter.start()
    threads = [
        threading.Thread(target=adapter.run, name=f"binance-{adapter.stream_key.channel}")
        for adapter in adapters
    ]
    for thread in threads:
        thread.start()
    try:
        while True:
            time.sleep(1)
    finally:
        for adapter in adapters:
            adapter.stop()
        for thread in threads:
            thread.join(timeout=1)
        runtime.orchestrator.stop()
        runtime.dashboards.stop()


if __name__ == "__main__":
    main()
