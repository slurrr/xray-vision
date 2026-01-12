from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from importlib import resources

from market_data.config import (
    BackpressureConfig,
    MarketDataConfig,
    MarketDataDefaults,
    OperationalLimits,
    RetryPolicy,
    SourceConfig,
    validate_config,
)

_DEFAULT_KEYS = {"defaults", "sources"}
_DEFAULT_LIMIT_KEYS = {"connect_timeout_ms", "read_timeout_ms", "retry", "backpressure"}
_DEFAULT_RETRY_KEYS = {"min_delay_ms", "max_delay_ms", "max_attempts", "max_elapsed_ms"}
_DEFAULT_BACKPRESSURE_KEYS = {"policy", "max_pending", "max_block_ms"}
_DEFAULT_SOURCE_KEYS = {"source_id", "symbol_map", "channels", "transport", "limits"}
_DEFAULT_ADAPTER_KEYS = {
    "agg_trade",
    "kline",
    "open_interest",
    "book_ticker",
    "depth",
    "mark_price",
    "force_order",
}


def load_default_config() -> MarketDataConfig:
    payload = _load_default_payload()
    config = _parse_config(payload)
    validate_config(config)
    return config


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("market_data.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("market_data default config must be a mapping")
    return data


def _parse_config(payload: Mapping[str, object]) -> MarketDataConfig:
    _reject_unknown(payload, _DEFAULT_KEYS, "market_data config")
    defaults = _parse_defaults(payload.get("defaults"))
    sources = _parse_sources(payload.get("sources"))
    return MarketDataConfig(defaults=defaults, sources=sources)

def _parse_defaults(payload: object) -> MarketDataDefaults:
    if not isinstance(payload, Mapping):
        raise ValueError("defaults must be a mapping")
    _reject_unknown(payload, {"symbol", "adapters", "backpressure", "limits"}, "defaults")
    symbol = payload.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("defaults.symbol must be set")
    adapters = payload.get("adapters")
    if not isinstance(adapters, Mapping):
        raise ValueError("defaults.adapters must be a mapping")
    _reject_unknown(adapters, _DEFAULT_ADAPTER_KEYS, "adapters")
    for key in _DEFAULT_ADAPTER_KEYS:
        if key not in adapters:
            raise ValueError(f"missing adapters.{key}")
        if not isinstance(adapters[key], bool):
            raise ValueError(f"adapters.{key} must be boolean")
    backpressure = _parse_backpressure(payload.get("backpressure"), "defaults.backpressure")
    limits = _parse_limits(payload.get("limits"), "defaults.limits")
    return MarketDataDefaults(
        symbol=symbol,
        adapters=adapters,
        backpressure=backpressure,
        limits=limits,
    )


def _parse_sources(payload: object) -> tuple[SourceConfig, ...]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        raise ValueError("sources must be a list")
    sources: list[SourceConfig] = []
    for item in payload:
        if not isinstance(item, Mapping):
            raise ValueError("source entries must be mappings")
        _reject_unknown(item, _DEFAULT_SOURCE_KEYS, "source")
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be set for each source")
        symbol_map = item.get("symbol_map")
        if not isinstance(symbol_map, Mapping):
            raise ValueError(f"symbol_map must be set for source_id={source_id}")
        channels = item.get("channels")
        if not isinstance(channels, Sequence) or isinstance(channels, (str, bytes)):
            raise ValueError(f"channels must be set for source_id={source_id}")
        transport = item.get("transport")
        if transport is not None and not isinstance(transport, Mapping):
            raise ValueError(f"transport must be a mapping for source_id={source_id}")
        limits = _parse_limits(item.get("limits"), f"limits for source_id={source_id}")
        sources.append(
            SourceConfig(
                source_id=source_id,
                symbol_map={str(key): str(value) for key, value in symbol_map.items()},
                channels=[str(value) for value in channels],
                transport=transport,
                limits=limits,
            )
        )
    return tuple(sources)


def _parse_limits(data: object, label: str) -> OperationalLimits | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    _reject_unknown(data, _DEFAULT_LIMIT_KEYS, label)
    connect_timeout_ms = data.get("connect_timeout_ms")
    read_timeout_ms = data.get("read_timeout_ms")
    if not isinstance(connect_timeout_ms, int):
        raise ValueError(f"{label}.connect_timeout_ms must be an int")
    if not isinstance(read_timeout_ms, int):
        raise ValueError(f"{label}.read_timeout_ms must be an int")
    retry = _parse_retry(data.get("retry"), f"{label}.retry")
    backpressure = _parse_backpressure(data.get("backpressure"), f"{label}.backpressure")
    return OperationalLimits(
        connect_timeout_ms=connect_timeout_ms,
        read_timeout_ms=read_timeout_ms,
        retry=retry,
        backpressure=backpressure,
    )


def _parse_retry(data: object, label: str) -> RetryPolicy:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    _reject_unknown(data, _DEFAULT_RETRY_KEYS, label)
    min_delay_ms = data.get("min_delay_ms")
    max_delay_ms = data.get("max_delay_ms")
    max_attempts = data.get("max_attempts")
    max_elapsed_ms = data.get("max_elapsed_ms")
    if not isinstance(min_delay_ms, int):
        raise ValueError(f"{label}.min_delay_ms must be an int")
    if not isinstance(max_delay_ms, int):
        raise ValueError(f"{label}.max_delay_ms must be an int")
    if not isinstance(max_attempts, int):
        raise ValueError(f"{label}.max_attempts must be an int")
    if max_elapsed_ms is not None and not isinstance(max_elapsed_ms, int):
        raise ValueError(f"{label}.max_elapsed_ms must be an int")
    return RetryPolicy(
        min_delay_ms=min_delay_ms,
        max_delay_ms=max_delay_ms,
        max_attempts=max_attempts,
        max_elapsed_ms=max_elapsed_ms,
    )


def _parse_backpressure(data: object, label: str) -> BackpressureConfig:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    _reject_unknown(data, _DEFAULT_BACKPRESSURE_KEYS, label)
    policy = data.get("policy")
    max_pending = data.get("max_pending")
    max_block_ms = data.get("max_block_ms")
    if not isinstance(policy, str) or not policy:
        raise ValueError(f"{label}.policy must be set")
    if not isinstance(max_pending, int):
        raise ValueError(f"{label}.max_pending must be an int")
    if max_block_ms is not None and not isinstance(max_block_ms, int):
        raise ValueError(f"{label}.max_block_ms must be an int")
    return BackpressureConfig(
        policy=policy,
        max_pending=max_pending,
        max_block_ms=max_block_ms,
    )


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
