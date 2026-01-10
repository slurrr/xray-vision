from __future__ import annotations

import json
from collections.abc import Mapping
from importlib import resources

from market_data.config import BackpressureConfig
from market_data.runtime_config import AdapterType, MarketDataRuntimeConfig

_ADAPTER_KEY_MAP: Mapping[str, AdapterType] = {
    "agg_trade": AdapterType.AGG_TRADE,
    "kline": AdapterType.KLINE,
    "open_interest": AdapterType.OPEN_INTEREST,
    "book_ticker": AdapterType.BOOK_TICKER,
    "depth": AdapterType.DEPTH,
    "mark_price": AdapterType.MARK_PRICE,
    "force_order": AdapterType.FORCE_ORDER,
}


def load_default_config() -> MarketDataRuntimeConfig:
    payload = _load_default_payload()
    return _parse_runtime_config(payload)


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("market_data.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    data = json.loads(text)
    if not isinstance(data, Mapping):
        raise ValueError("market_data default config must be a mapping")
    return data


def _parse_runtime_config(payload: Mapping[str, object]) -> MarketDataRuntimeConfig:
    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("market_data config requires non-empty symbol")
    backpressure = _parse_backpressure(payload.get("backpressure"))
    enabled_adapters = _parse_enabled_adapters(payload.get("adapters"))
    return MarketDataRuntimeConfig(
        symbol=symbol,
        enabled_adapters=frozenset(enabled_adapters),
        backpressure=backpressure,
    )


def _parse_backpressure(data: object) -> BackpressureConfig:
    if not isinstance(data, Mapping):
        raise ValueError("market_data config requires backpressure mapping")
    policy = data.get("policy")
    max_pending = data.get("max_pending")
    max_block_ms = data.get("max_block_ms")
    if not isinstance(policy, str) or not policy:
        raise ValueError("backpressure.policy must be set")
    if not isinstance(max_pending, int):
        raise ValueError("backpressure.max_pending must be an int")
    if max_block_ms is not None and not isinstance(max_block_ms, int):
        raise ValueError("backpressure.max_block_ms must be an int")
    return BackpressureConfig(
        policy=policy,
        max_pending=max_pending,
        max_block_ms=max_block_ms,
    )


def _parse_enabled_adapters(data: object) -> frozenset[AdapterType]:
    if not isinstance(data, Mapping):
        raise ValueError("market_data config requires adapters mapping")
    enabled: set[AdapterType] = set()
    for key, adapter_type in _ADAPTER_KEY_MAP.items():
        if key not in data:
            raise ValueError(f"missing adapters.{key}")
        value = data[key]
        if not isinstance(value, bool):
            raise ValueError(f"adapters.{key} must be boolean")
        if value:
            enabled.add(adapter_type)
    unknown = set(data.keys()) - set(_ADAPTER_KEY_MAP.keys())
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown adapter keys: {unknown_list}")
    return frozenset(enabled)
