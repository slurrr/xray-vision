from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from market_data.contracts import RawMarketEvent
from market_data.pipeline import IngestionPipeline


@dataclass(frozen=True)
class DecodeFailureDetail:
    error_kind: str
    error_detail: str


class DecodeError(Exception):
    def __init__(self, detail: DecodeFailureDetail) -> None:
        super().__init__(detail.error_detail)
        self.detail = detail


def decode_and_ingest(
    *,
    pipeline: IngestionPipeline,
    event_type: str,
    source_id: str,
    symbol: str,
    exchange_ts_ms: int | None,
    raw_payload: bytes | str,
    payload_content_type: str | None = None,
    source_event_id: str | None = None,
    source_seq: int | None = None,
    channel: str | None = None,
    payload_hash: str | None = None,
) -> RawMarketEvent:
    try:
        decoded = _decode_payload(raw_payload, payload_content_type)
        normalized = _map_normalized(event_type, decoded)
        return pipeline.ingest(
            event_type=event_type,
            source_id=source_id,
            symbol=symbol,
            exchange_ts_ms=exchange_ts_ms,
            raw_payload=raw_payload,
            normalized=normalized,
            source_event_id=source_event_id,
            source_seq=source_seq,
            channel=channel,
            payload_content_type=payload_content_type,
            payload_hash=payload_hash,
        )
    except DecodeError as exc:
        return pipeline.ingest(
            event_type="DecodeFailure",
            source_id=source_id,
            symbol=symbol,
            exchange_ts_ms=exchange_ts_ms,
            raw_payload=raw_payload,
            normalized={
                "error_kind": exc.detail.error_kind,
                "error_detail": exc.detail.error_detail,
            },
            source_event_id=source_event_id,
            source_seq=source_seq,
            channel=channel,
            payload_content_type=payload_content_type,
            payload_hash=payload_hash,
        )


def _decode_payload(raw_payload: bytes | str, payload_content_type: str | None) -> Any:
    if payload_content_type is not None and "json" not in payload_content_type:
        raise DecodeError(DecodeFailureDetail("decode_error", "unsupported content type"))

    try:
        if isinstance(raw_payload, bytes):
            text = raw_payload.decode("utf-8")
        else:
            text = raw_payload
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DecodeError(DecodeFailureDetail("decode_error", str(exc))) from exc


def _map_normalized(event_type: str, payload: Any) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise DecodeError(DecodeFailureDetail("schema_mismatch", "payload must be an object"))

    mapper = _EVENT_MAPPERS.get(event_type)
    if mapper is None:
        raise DecodeError(DecodeFailureDetail("schema_mismatch", "unsupported event_type"))
    return mapper(payload)


def _require_field(payload: Mapping[str, Any], key: str) -> Any:
    if key not in payload:
        raise DecodeError(DecodeFailureDetail("missing_required_field", f"missing {key}"))
    return payload[key]


def _parse_number(value: Any, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}")) from exc
    raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}"))


def _parse_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}"))
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}")) from exc
    raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}"))


def _parse_side(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"buy", "sell"}:
            return lowered
    raise DecodeError(DecodeFailureDetail("parse_error", "invalid side"))


def _parse_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
    raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}"))


def _map_trade_tick(payload: Mapping[str, Any]) -> Mapping[str, object]:
    price = _parse_number(_require_field(payload, "price"), "price")
    quantity = _parse_number(_require_field(payload, "quantity"), "quantity")
    side_value = payload.get("side")
    side = _parse_side(side_value) if side_value is not None else None
    return {"price": price, "quantity": quantity, "side": side}


def _map_book_top(payload: Mapping[str, Any]) -> Mapping[str, object]:
    return {
        "best_bid_price": _parse_number(_require_field(payload, "best_bid_price"), "best_bid_price"),
        "best_bid_quantity": _parse_number(
            _require_field(payload, "best_bid_quantity"), "best_bid_quantity"
        ),
        "best_ask_price": _parse_number(_require_field(payload, "best_ask_price"), "best_ask_price"),
        "best_ask_quantity": _parse_number(
            _require_field(payload, "best_ask_quantity"), "best_ask_quantity"
        ),
    }


def _parse_levels(levels: Any, field: str) -> list[list[float]]:
    if not isinstance(levels, list):
        raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}"))
    parsed: list[list[float]] = []
    for entry in levels:
        if not isinstance(entry, list) or len(entry) != 2:
            raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {field}"))
        price = _parse_number(entry[0], f"{field}.price")
        quantity = _parse_number(entry[1], f"{field}.quantity")
        parsed.append([price, quantity])
    return parsed


def _map_book_delta(payload: Mapping[str, Any]) -> Mapping[str, object]:
    bids = _parse_levels(_require_field(payload, "bids"), "bids")
    asks = _parse_levels(_require_field(payload, "asks"), "asks")
    return {"bids": bids, "asks": asks}


def _map_candle(payload: Mapping[str, Any]) -> Mapping[str, object]:
    is_final = payload.get("is_final")
    parsed_is_final = None if is_final is None else _parse_bool(is_final, "is_final")
    return {
        "open": _parse_number(_require_field(payload, "open"), "open"),
        "high": _parse_number(_require_field(payload, "high"), "high"),
        "low": _parse_number(_require_field(payload, "low"), "low"),
        "close": _parse_number(_require_field(payload, "close"), "close"),
        "volume": _parse_number(_require_field(payload, "volume"), "volume"),
        "interval_ms": _parse_int(_require_field(payload, "interval_ms"), "interval_ms"),
        "is_final": parsed_is_final,
    }


def _map_funding_rate(payload: Mapping[str, Any]) -> Mapping[str, object]:
    return {"funding_rate": _parse_number(_require_field(payload, "funding_rate"), "funding_rate")}


def _map_open_interest(payload: Mapping[str, Any]) -> Mapping[str, object]:
    return {
        "open_interest": _parse_number(_require_field(payload, "open_interest"), "open_interest")
    }


def _map_mark_price(payload: Mapping[str, Any]) -> Mapping[str, object]:
    return {"mark_price": _parse_number(_require_field(payload, "mark_price"), "mark_price")}


def _map_index_price(payload: Mapping[str, Any]) -> Mapping[str, object]:
    return {"index_price": _parse_number(_require_field(payload, "index_price"), "index_price")}


def _map_liquidation_print(payload: Mapping[str, Any]) -> Mapping[str, object]:
    price = _parse_number(_require_field(payload, "price"), "price")
    quantity = _parse_number(_require_field(payload, "quantity"), "quantity")
    side_value = payload.get("side")
    side = _parse_side(side_value) if side_value is not None else None
    return {"price": price, "quantity": quantity, "side": side}


def _map_snapshot_inputs(payload: Mapping[str, Any]) -> Mapping[str, object]:
    timestamp_ms = _parse_int(_require_field(payload, "timestamp_ms"), "timestamp_ms")
    normalized: dict[str, object] = {"timestamp_ms": timestamp_ms}
    for key in ("market", "derivatives", "flow", "context"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, Mapping):
                raise DecodeError(DecodeFailureDetail("parse_error", f"invalid {key}"))
            normalized[key] = value
    return normalized


_EVENT_MAPPERS = {
    "TradeTick": _map_trade_tick,
    "BookTop": _map_book_top,
    "BookDelta": _map_book_delta,
    "Candle": _map_candle,
    "FundingRate": _map_funding_rate,
    "OpenInterest": _map_open_interest,
    "MarkPrice": _map_mark_price,
    "IndexPrice": _map_index_price,
    "LiquidationPrint": _map_liquidation_print,
    "SnapshotInputs": _map_snapshot_inputs,
}
