from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_ADAPTER_KEYS: tuple[str, ...] = (
    "agg_trade",
    "kline",
    "open_interest",
    "book_ticker",
    "depth",
    "mark_price",
    "force_order",
)


@dataclass(frozen=True)
class RetryPolicy:
    min_delay_ms: int
    max_delay_ms: int
    max_attempts: int
    max_elapsed_ms: int | None = None


@dataclass(frozen=True)
class BackpressureConfig:
    policy: str
    max_pending: int
    max_block_ms: int | None = None


@dataclass(frozen=True)
class OperationalLimits:
    connect_timeout_ms: int
    read_timeout_ms: int
    retry: RetryPolicy
    backpressure: BackpressureConfig


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    symbol_map: Mapping[str, str]
    channels: Sequence[str]
    transport: Mapping[str, object] | None = None
    limits: OperationalLimits | None = None


@dataclass(frozen=True)
class MarketDataDefaults:
    symbol: str
    adapters: Mapping[str, bool]
    backpressure: BackpressureConfig
    limits: OperationalLimits | None = None


@dataclass(frozen=True)
class MarketDataConfig:
    defaults: MarketDataDefaults
    sources: Sequence[SourceConfig]


def validate_config(config: MarketDataConfig) -> None:
    _validate_defaults(config.defaults)

    if not config.sources:
        raise ValueError("market_data config must include at least one source")

    source_ids: set[str] = set()
    for source in config.sources:
        if not source.source_id:
            raise ValueError("source_id must be set for each source")
        if source.source_id in source_ids:
            raise ValueError(f"duplicate source_id: {source.source_id}")
        source_ids.add(source.source_id)

        if not source.symbol_map:
            raise ValueError(f"symbol_map must be set for source_id={source.source_id}")

        if not source.channels:
            raise ValueError(f"channels must be set for source_id={source.source_id}")

        if source.limits is None:
            continue

        limits = source.limits
        _require_positive(limits.connect_timeout_ms, "connect_timeout_ms")
        _require_positive(limits.read_timeout_ms, "read_timeout_ms")
        _validate_retry(limits.retry)
        _validate_backpressure(limits.backpressure)


def _validate_defaults(defaults: MarketDataDefaults) -> None:
    if not defaults.symbol:
        raise ValueError("defaults.symbol must be set")
    _validate_adapters(defaults.adapters)
    _validate_backpressure(defaults.backpressure)
    if defaults.limits is None:
        return
    limits = defaults.limits
    _require_positive(limits.connect_timeout_ms, "connect_timeout_ms")
    _require_positive(limits.read_timeout_ms, "read_timeout_ms")
    _validate_retry(limits.retry)
    _validate_backpressure(limits.backpressure)


def _validate_adapters(adapters: Mapping[str, bool]) -> None:
    for key in _ADAPTER_KEYS:
        if key not in adapters:
            raise ValueError(f"missing adapters.{key}")
        if not isinstance(adapters[key], bool):
            raise ValueError(f"adapters.{key} must be boolean")
    unknown = set(adapters.keys()) - set(_ADAPTER_KEYS)
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown adapter keys: {unknown_list}")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")


def _validate_retry(retry: RetryPolicy) -> None:
    _require_positive(retry.min_delay_ms, "retry.min_delay_ms")
    _require_positive(retry.max_delay_ms, "retry.max_delay_ms")
    if retry.max_delay_ms < retry.min_delay_ms:
        raise ValueError("retry.max_delay_ms must be >= retry.min_delay_ms")
    if retry.max_attempts <= 0:
        raise ValueError("retry.max_attempts must be > 0")
    if retry.max_elapsed_ms is not None:
        _require_positive(retry.max_elapsed_ms, "retry.max_elapsed_ms")


def _validate_backpressure(backpressure: BackpressureConfig) -> None:
    if backpressure.policy not in {"block", "fail"}:
        raise ValueError("backpressure.policy must be 'block' or 'fail'")
    if backpressure.max_pending <= 0:
        raise ValueError("backpressure.max_pending must be > 0")
    if backpressure.max_block_ms is not None:
        if not isinstance(backpressure.max_block_ms, int):
            raise ValueError("backpressure.max_block_ms must be an int")
        if backpressure.max_block_ms <= 0:
            raise ValueError("backpressure.max_block_ms must be > 0")

