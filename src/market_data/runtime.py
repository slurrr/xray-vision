from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from market_data.adapter import Adapter
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
from market_data.observability import Observability, set_observability
from market_data.pipeline import IngestionPipeline
from market_data.runtime_config import AdapterType, MarketDataRuntimeConfig
from market_data.sink import RawEventSink


@dataclass(frozen=True)
class MarketDataRuntimeInfo:
    symbol: str
    adapter_count: int
    optional_enabled: bool


class MarketDataRuntime:
    def __init__(
        self,
        *,
        adapters: Iterable[Adapter],
        threads: Iterable[threading.Thread],
        info: MarketDataRuntimeInfo,
    ) -> None:
        self._adapters = list(adapters)
        self._threads = list(threads)
        self._info = info

    @property
    def info(self) -> MarketDataRuntimeInfo:
        return self._info

    def start(self) -> None:
        for adapter in self._adapters:
            adapter.start()
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        for adapter in self._adapters:
            adapter.stop()
        for thread in self._threads:
            thread.join(timeout=1)


def build_market_data_runtime(
    *,
    sink: RawEventSink,
    observability: Observability,
    config: MarketDataRuntimeConfig | None = None,
) -> MarketDataRuntime:
    set_observability(observability)
    runtime_config = config or MarketDataRuntimeConfig.default()
    pipeline = IngestionPipeline(
        sink=sink,
        backpressure=runtime_config.backpressure,
        observability=observability,
    )
    adapters = _build_binance_adapters(
        config=runtime_config,
        pipeline=pipeline,
        observability=observability,
    )
    threads = [
        threading.Thread(
            target=adapter.run,
            name=f"binance-{adapter.stream_key.channel}",
        )
        for adapter in adapters
    ]
    info = MarketDataRuntimeInfo(
        symbol=runtime_config.symbol,
        adapter_count=len(adapters),
        optional_enabled=runtime_config.optional_enabled,
    )
    return MarketDataRuntime(adapters=adapters, threads=threads, info=info)


def _build_binance_adapters(
    *,
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> list[Adapter]:
    adapters: list[Adapter] = []
    for adapter_type in config.iter_enabled_adapters():
        factory = _ADAPTER_FACTORIES.get(adapter_type)
        if factory is None:
            raise ValueError(f"unsupported adapter: {adapter_type}")
        adapters.append(factory(config, pipeline, observability))
    return adapters


def _build_agg_trade_adapter(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceAggTradeAdapter(
        config=BinanceAggTradeConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


def _build_kline_adapter(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceKlineAdapter(
        config=BinanceKlineConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


def _build_open_interest_poller(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceOpenInterestPoller(
        config=BinanceOpenInterestConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


def _build_book_ticker_adapter(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceBookTickerAdapter(
        config=BinanceBookTickerConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


def _build_depth_adapter(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceDepthAdapter(
        config=BinanceDepthConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


def _build_mark_price_adapter(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceMarkPriceAdapter(
        config=BinanceMarkPriceConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


def _build_force_order_adapter(
    config: MarketDataRuntimeConfig,
    pipeline: IngestionPipeline,
    observability: Observability,
) -> Adapter:
    return BinanceForceOrderAdapter(
        config=BinanceForceOrderConfig.default(symbol=config.symbol),
        pipeline=pipeline,
        observability=observability,
    )


_ADAPTER_FACTORIES: dict[
    AdapterType, Callable[[MarketDataRuntimeConfig, IngestionPipeline, Observability], Adapter]
] = {
    AdapterType.AGG_TRADE: _build_agg_trade_adapter,
    AdapterType.KLINE: _build_kline_adapter,
    AdapterType.OPEN_INTEREST: _build_open_interest_poller,
    AdapterType.BOOK_TICKER: _build_book_ticker_adapter,
    AdapterType.DEPTH: _build_depth_adapter,
    AdapterType.MARK_PRICE: _build_mark_price_adapter,
    AdapterType.FORCE_ORDER: _build_force_order_adapter,
}
