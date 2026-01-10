from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType

from composer.contracts.feature_snapshot import (
    FEATURE_KEYS_V1_CANONICAL,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    FeatureSnapshot,
)
from composer.contracts.ordering import ordered_feature_items
from market_data.contracts import RawMarketEvent

WINDOW_3M_MS = 180_000
ATR_WINDOW = 14
ATR_Z_WINDOW = 50


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def _trade_events(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> list[RawMarketEvent]:
    trades: list[RawMarketEvent] = []
    for event in events:
        if event.symbol != symbol or event.event_type != "TradeTick":
            continue
        ts = event.exchange_ts_ms
        if ts is None:
            continue
        if start_ms is not None and ts < start_ms:
            continue
        if end_ms is not None and ts > end_ms:
            continue
        trades.append(event)
    return trades


def _latest_trade_price(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> float | None:
    latest: float | None = None
    for event in events:
        if event.symbol != symbol or event.event_type != "TradeTick":
            continue
        ts = event.exchange_ts_ms
        if ts is None or ts > engine_timestamp_ms:
            continue
        price = _as_float(event.normalized.get("price"))
        if price is None:
            continue
        latest = price
    return latest


def _vwap_3m(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> float | None:
    start_ms = engine_timestamp_ms - WINDOW_3M_MS
    trades = _trade_events(events, symbol=symbol, start_ms=start_ms, end_ms=engine_timestamp_ms)
    total_qty = 0.0
    total_notional = 0.0
    for trade in trades:
        price = _as_float(trade.normalized.get("price"))
        qty = _as_float(trade.normalized.get("quantity"))
        if price is None or qty is None or qty <= 0.0:
            continue
        total_qty += qty
        total_notional += price * qty
    if total_qty <= 0.0:
        return None
    return total_notional / total_qty


def _cvd_3m(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> float | None:
    start_ms = engine_timestamp_ms - WINDOW_3M_MS
    trades = _trade_events(events, symbol=symbol, start_ms=start_ms, end_ms=engine_timestamp_ms)
    total = 0.0
    eligible = 0
    for trade in trades:
        side = trade.normalized.get("side")
        if side not in {"buy", "sell"}:
            continue
        qty = _as_float(trade.normalized.get("quantity"))
        if qty is None or qty <= 0.0:
            continue
        eligible += 1
        if side == "buy":
            total += qty
        else:
            total -= qty
    if eligible == 0:
        return None
    return total


def _aggressive_volume_ratio_3m(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> float | None:
    start_ms = engine_timestamp_ms - WINDOW_3M_MS
    trades = _trade_events(events, symbol=symbol, start_ms=start_ms, end_ms=engine_timestamp_ms)
    buy_qty = 0.0
    sell_qty = 0.0
    for trade in trades:
        side = trade.normalized.get("side")
        if side not in {"buy", "sell"}:
            continue
        qty = _as_float(trade.normalized.get("quantity"))
        if qty is None or qty <= 0.0:
            continue
        if side == "buy":
            buy_qty += qty
        else:
            sell_qty += qty
    total = buy_qty + sell_qty
    if total <= 0.0:
        return None
    return buy_qty / total


def _eligible_candles(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> list[tuple[int, int, float, float, float]]:
    candles: list[tuple[int, int, float, float, float]] = []
    for index, event in enumerate(events):
        if event.symbol != symbol or event.event_type != "Candle":
            continue
        ts = event.exchange_ts_ms
        if ts is None or ts > engine_timestamp_ms:
            continue
        interval_ms = event.normalized.get("interval_ms")
        if interval_ms != WINDOW_3M_MS:
            continue
        if event.normalized.get("is_final") is not True:
            continue
        high = _as_float(event.normalized.get("high"))
        low = _as_float(event.normalized.get("low"))
        close = _as_float(event.normalized.get("close"))
        if high is None or low is None or close is None:
            continue
        candles.append((ts, index, high, low, close))
    candles.sort(key=lambda item: (item[0], item[1]))
    return candles


def _atr_14(
    candles: Sequence[tuple[int, int, float, float, float]],
) -> tuple[float | None, list[float]]:
    true_ranges: list[float] = []
    prev_close: float | None = None
    for _, _, high, low, close in candles:
        if prev_close is None:
            true_range = high - low
        else:
            true_range = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )
        true_ranges.append(true_range)
        prev_close = close
    if len(true_ranges) < ATR_WINDOW:
        return None, true_ranges
    window = true_ranges[-ATR_WINDOW:]
    return sum(window) / ATR_WINDOW, true_ranges


def _atr_z_50(true_ranges: Sequence[float]) -> float | None:
    if len(true_ranges) < ATR_WINDOW:
        return None
    atr_series: list[float] = []
    for end_index in range(ATR_WINDOW - 1, len(true_ranges)):
        window = true_ranges[end_index - (ATR_WINDOW - 1) : end_index + 1]
        atr_series.append(sum(window) / ATR_WINDOW)
    if len(atr_series) < ATR_Z_WINDOW:
        return None
    window = atr_series[-ATR_Z_WINDOW:]
    mean = sum(window) / ATR_Z_WINDOW
    variance = sum((value - mean) ** 2 for value in window) / ATR_Z_WINDOW
    if variance <= 0.0:
        return None
    return (atr_series[-1] - mean) / math.sqrt(variance)


def _open_interest_latest(
    events: Sequence[RawMarketEvent],
    *,
    symbol: str,
) -> float | None:
    best_value: float | None = None
    best_ts: int | None = None
    fallback_value: float | None = None
    for event in events:
        if event.symbol != symbol or event.event_type != "OpenInterest":
            continue
        value = _as_float(event.normalized.get("open_interest"))
        if value is None:
            continue
        ts = event.exchange_ts_ms
        if ts is None:
            fallback_value = value
            continue
        if best_ts is None or ts > best_ts:
            best_ts = ts
            best_value = value
        elif ts == best_ts:
            best_value = value
    if best_ts is not None:
        return best_value
    return fallback_value


def compute_feature_snapshot(
    raw_events: Iterable[RawMarketEvent],
    *,
    symbol: str,
    engine_timestamp_ms: int,
) -> FeatureSnapshot:
    events = tuple(raw_events)
    price_last = _latest_trade_price(
        events, symbol=symbol, engine_timestamp_ms=engine_timestamp_ms
    )
    vwap_3m = _vwap_3m(events, symbol=symbol, engine_timestamp_ms=engine_timestamp_ms)
    cvd_3m = _cvd_3m(events, symbol=symbol, engine_timestamp_ms=engine_timestamp_ms)
    aggressive_ratio = _aggressive_volume_ratio_3m(
        events, symbol=symbol, engine_timestamp_ms=engine_timestamp_ms
    )
    candles = _eligible_candles(events, symbol=symbol, engine_timestamp_ms=engine_timestamp_ms)
    atr_14, true_ranges = _atr_14(candles)
    atr_z_50 = _atr_z_50(true_ranges)
    open_interest_latest = _open_interest_latest(events, symbol=symbol)

    features: Mapping[str, float | None] = {
        "price_last": price_last,
        "vwap_3m": vwap_3m,
        "atr_14": atr_14,
        "atr_z_50": atr_z_50,
        "cvd_3m": cvd_3m,
        "aggressive_volume_ratio_3m": aggressive_ratio,
        "open_interest_latest": open_interest_latest,
    }
    if set(features.keys()) != set(FEATURE_KEYS_V1_CANONICAL):
        raise ValueError("feature key set mismatch")
    ordered_features = {key: value for key, value in ordered_feature_items(features)}
    return FeatureSnapshot(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        features=MappingProxyType(ordered_features),
    )
