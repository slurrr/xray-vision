from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class DecodeError(Exception):
    error_kind: str
    error_detail: str


@dataclass(frozen=True)
class DecodedEvent:
    event_type: str
    exchange_ts_ms: int | None
    normalized: Mapping[str, object]
    source_event_id: str | None = None
    source_seq: int | None = None


@dataclass(frozen=True)
class DecodedEvents:
    events: tuple[DecodedEvent, ...]
    errors: tuple[DecodeError, ...]


def decode_agg_trade(payload: Mapping[str, object]) -> DecodedEvent:
    exchange_ts_ms = _as_int(payload.get("T"), key="T")
    price = _as_float(payload.get("p"), key="p")
    quantity = _as_float(payload.get("q"), key="q")
    source_event_id = _as_str_optional(payload.get("a"))
    side = _side_from_maker(payload.get("m"))
    return DecodedEvent(
        event_type="TradeTick",
        exchange_ts_ms=exchange_ts_ms,
        normalized={"price": price, "quantity": quantity, "side": side},
        source_event_id=source_event_id,
    )


def decode_kline(payload: Mapping[str, object]) -> DecodedEvent:
    kline = _require_mapping(payload, "k")
    interval = _as_str(kline.get("i"), key="k.i")
    if interval != "3m":
        raise DecodeError("schema_mismatch", f"unexpected interval: {interval}")

    exchange_ts_ms = _as_int_optional(kline.get("T"), key="k.T")
    if exchange_ts_ms is None:
        exchange_ts_ms = _as_int(payload.get("E"), key="E")
    open_price = _as_float(kline.get("o"), key="k.o")
    high_price = _as_float(kline.get("h"), key="k.h")
    low_price = _as_float(kline.get("l"), key="k.l")
    close_price = _as_float(kline.get("c"), key="k.c")
    volume = _as_float(kline.get("v"), key="k.v")
    is_final = _as_bool_optional(kline.get("x"), key="k.x")
    return DecodedEvent(
        event_type="Candle",
        exchange_ts_ms=exchange_ts_ms,
        normalized={
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volume,
            "interval_ms": 180000,
            "is_final": is_final,
        },
    )


def decode_book_ticker(payload: Mapping[str, object]) -> DecodedEvent:
    best_bid_price = _as_float(payload.get("b"), key="b")
    best_bid_quantity = _as_float(payload.get("B"), key="B")
    best_ask_price = _as_float(payload.get("a"), key="a")
    best_ask_quantity = _as_float(payload.get("A"), key="A")
    exchange_ts_ms = _as_int_optional(payload.get("E"), key="E")
    return DecodedEvent(
        event_type="BookTop",
        exchange_ts_ms=exchange_ts_ms,
        normalized={
            "best_bid_price": best_bid_price,
            "best_bid_quantity": best_bid_quantity,
            "best_ask_price": best_ask_price,
            "best_ask_quantity": best_ask_quantity,
        },
    )


def decode_depth(payload: Mapping[str, object]) -> DecodedEvent:
    bids = _as_price_levels(payload.get("b"), key="b")
    asks = _as_price_levels(payload.get("a"), key="a")
    exchange_ts_ms = _as_int_optional(payload.get("E"), key="E")
    source_seq = _as_int_optional(payload.get("u"), key="u")
    return DecodedEvent(
        event_type="BookDelta",
        exchange_ts_ms=exchange_ts_ms,
        normalized={"bids": bids, "asks": asks},
        source_seq=source_seq,
    )


def decode_mark_price(payload: Mapping[str, object]) -> DecodedEvents:
    exchange_ts_ms = _as_int_optional(payload.get("E"), key="E")
    events: list[DecodedEvent] = []
    errors: list[DecodeError] = []
    mappings = (
        ("p", "MarkPrice", "mark_price"),
        ("i", "IndexPrice", "index_price"),
        ("r", "FundingRate", "funding_rate"),
    )
    for key, event_type, normalized_key in mappings:
        try:
            value = _as_float(payload.get(key), key=key)
        except DecodeError as exc:
            errors.append(exc)
            continue
        events.append(
            DecodedEvent(
                event_type=event_type,
                exchange_ts_ms=exchange_ts_ms,
                normalized={normalized_key: value},
            )
        )
    return DecodedEvents(events=tuple(events), errors=tuple(errors))


def decode_force_order(payload: Mapping[str, object]) -> DecodedEvent:
    order = _require_mapping(payload, "o")
    exchange_ts_ms = _as_int_optional(order.get("T"), key="o.T")
    price = _as_float(order.get("p"), key="o.p")
    quantity = _as_float(order.get("q"), key="o.q")
    side = _side_from_order(order.get("S"))
    return DecodedEvent(
        event_type="LiquidationPrint",
        exchange_ts_ms=exchange_ts_ms,
        normalized={"price": price, "quantity": quantity, "side": side},
    )


def decode_open_interest(payload: Mapping[str, object]) -> DecodedEvent:
    open_interest = _as_float(payload.get("openInterest"), key="openInterest")
    exchange_ts_ms = _as_int_optional(payload.get("time"), key="time")
    return DecodedEvent(
        event_type="OpenInterest",
        exchange_ts_ms=exchange_ts_ms,
        normalized={"open_interest": open_interest},
    )


def _require_mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if isinstance(value, Mapping):
        return value
    raise DecodeError("schema_mismatch", f"missing {key}")


def _as_int(value: object, *, key: str) -> int:
    if isinstance(value, bool):
        raise DecodeError("schema_mismatch", f"invalid {key}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise DecodeError("schema_mismatch", f"invalid {key}") from exc
    raise DecodeError("schema_mismatch", f"missing {key}")


def _as_int_optional(value: object, *, key: str) -> int | None:
    if value is None:
        return None
    return _as_int(value, key=key)


def _as_float(value: object, *, key: str) -> float:
    if isinstance(value, bool):
        raise DecodeError("schema_mismatch", f"invalid {key}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise DecodeError("schema_mismatch", f"invalid {key}") from exc
    raise DecodeError("schema_mismatch", f"missing {key}")


def _as_str(value: object, *, key: str) -> str:
    if isinstance(value, str):
        return value
    raise DecodeError("schema_mismatch", f"missing {key}")


def _as_str_optional(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return None


def _as_bool_optional(value: object, *, key: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
    raise DecodeError("schema_mismatch", f"invalid {key}")


def _as_price_levels(value: object, *, key: str) -> list[list[float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise DecodeError("schema_mismatch", f"invalid {key}")
    levels: list[list[float]] = []
    for entry in value:
        if not isinstance(entry, Sequence) or isinstance(entry, (str, bytes)):
            raise DecodeError("schema_mismatch", f"invalid {key}")
        if len(entry) < 2:
            raise DecodeError("schema_mismatch", f"invalid {key}")
        price = _as_float(entry[0], key=key)
        quantity = _as_float(entry[1], key=key)
        levels.append([price, quantity])
    return levels


def _side_from_maker(value: object) -> str | None:
    if isinstance(value, bool):
        return "sell" if value else "buy"
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "false"}:
            return "sell" if lowered == "true" else "buy"
    return None


def _side_from_order(value: object) -> str | None:
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"buy", "sell"}:
            return lowered
    return None
