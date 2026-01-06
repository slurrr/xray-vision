from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

SCHEMA_NAME = "raw_market_event"
SCHEMA_VERSION = "1"

EventType = Literal[
    "TradeTick",
    "BookTop",
    "BookDelta",
    "Candle",
    "FundingRate",
    "OpenInterest",
    "MarkPrice",
    "IndexPrice",
    "LiquidationPrint",
    "SnapshotInputs",
    "DecodeFailure",
]

EVENT_TYPES: Sequence[str] = (
    "TradeTick",
    "BookTop",
    "BookDelta",
    "Candle",
    "FundingRate",
    "OpenInterest",
    "MarkPrice",
    "IndexPrice",
    "LiquidationPrint",
    "SnapshotInputs",
    "DecodeFailure",
)

EVENT_TYPE_REQUIRED_NORMALIZED_KEYS: Mapping[str, frozenset[str]] = {
    "TradeTick": frozenset({"price", "quantity", "side"}),
    "BookTop": frozenset(
        {
            "best_bid_price",
            "best_bid_quantity",
            "best_ask_price",
            "best_ask_quantity",
        }
    ),
    "BookDelta": frozenset({"bids", "asks"}),
    "Candle": frozenset({"open", "high", "low", "close", "volume", "interval_ms", "is_final"}),
    "FundingRate": frozenset({"funding_rate"}),
    "OpenInterest": frozenset({"open_interest"}),
    "MarkPrice": frozenset({"mark_price"}),
    "IndexPrice": frozenset({"index_price"}),
    "LiquidationPrint": frozenset({"price", "quantity", "side"}),
    "SnapshotInputs": frozenset({"timestamp_ms"}),
    "DecodeFailure": frozenset({"error_kind", "error_detail"}),
}


@dataclass(frozen=True)
class RawMarketEvent:
    schema: str
    schema_version: str
    event_type: str
    source_id: str
    symbol: str
    exchange_ts_ms: int | None
    recv_ts_ms: int
    raw_payload: bytes | str
    normalized: Mapping[str, object]
    source_event_id: str | None = None
    source_seq: int | None = None
    channel: str | None = None
    payload_content_type: str | None = None
    payload_hash: str | None = None

