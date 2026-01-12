from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum

from market_data.config import BackpressureConfig


class AdapterType(str, Enum):
    AGG_TRADE = "agg_trade"
    KLINE = "kline"
    OPEN_INTEREST = "open_interest"
    BOOK_TICKER = "book_ticker"
    DEPTH = "depth"
    MARK_PRICE = "mark_price"
    FORCE_ORDER = "force_order"


_ADAPTER_ORDER: tuple[AdapterType, ...] = (
    AdapterType.AGG_TRADE,
    AdapterType.KLINE,
    AdapterType.OPEN_INTEREST,
    AdapterType.BOOK_TICKER,
    AdapterType.DEPTH,
    AdapterType.MARK_PRICE,
    AdapterType.FORCE_ORDER,
)

_OPTIONAL_ADAPTERS: frozenset[AdapterType] = frozenset(
    {
        AdapterType.BOOK_TICKER,
        AdapterType.DEPTH,
        AdapterType.MARK_PRICE,
        AdapterType.FORCE_ORDER,
    }
)


@dataclass(frozen=True)
class MarketDataRuntimeConfig:
    symbol: str
    enabled_adapters: frozenset[AdapterType]
    backpressure: BackpressureConfig

    def iter_enabled_adapters(self) -> tuple[AdapterType, ...]:
        return tuple(adapter for adapter in _ADAPTER_ORDER if adapter in self.enabled_adapters)

    @property
    def optional_enabled(self) -> bool:
        return any(adapter in _OPTIONAL_ADAPTERS for adapter in self.enabled_adapters)

    @classmethod
    def default(cls) -> MarketDataRuntimeConfig:
        warnings.warn(
            "MarketDataRuntimeConfig.default is deprecated; load MarketDataConfig and derive "
            "runtime config in market_data.runtime instead.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        from market_data.config.loader import load_default_config

        config = load_default_config()
        enabled: set[AdapterType] = set()
        for key, adapter_type in _ADAPTER_KEY_MAP.items():
            if config.defaults.adapters.get(key):
                enabled.add(adapter_type)
        return MarketDataRuntimeConfig(
            symbol=config.defaults.symbol,
            enabled_adapters=frozenset(enabled),
            backpressure=config.defaults.backpressure,
        )


_ADAPTER_KEY_MAP: dict[str, AdapterType] = {
    "agg_trade": AdapterType.AGG_TRADE,
    "kline": AdapterType.KLINE,
    "open_interest": AdapterType.OPEN_INTEREST,
    "book_ticker": AdapterType.BOOK_TICKER,
    "depth": AdapterType.DEPTH,
    "mark_price": AdapterType.MARK_PRICE,
    "force_order": AdapterType.FORCE_ORDER,
}
