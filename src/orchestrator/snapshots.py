from __future__ import annotations

from dataclasses import fields
from typing import Any, Mapping

from market_data.contracts import RawMarketEvent
from orchestrator.cuts import Cut
from orchestrator.buffer import RawInputBuffer
from regime_engine.contracts.snapshots import (
    MISSING,
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)


def select_snapshot_event(
    *,
    buffer: RawInputBuffer,
    cut: Cut,
    engine_timestamp_ms: int,
) -> RawMarketEvent | None:
    candidates = [
        record
        for record in buffer.range_by_seq(
            start_seq=cut.cut_start_ingest_seq, end_seq=cut.cut_end_ingest_seq
        )
        if record.event.event_type == "SnapshotInputs"
        and record.event.symbol == cut.symbol
        and record.event.normalized.get("timestamp_ms") == engine_timestamp_ms
    ]
    if not candidates:
        return None
    selected = max(candidates, key=lambda record: record.ingest_seq)
    return selected.event


def build_snapshot(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    snapshot_event: RawMarketEvent,
) -> RegimeInputSnapshot:
    normalized = snapshot_event.normalized
    market = _build_dataclass(MarketSnapshot, normalized.get("market"))
    derivatives = _build_dataclass(DerivativesSnapshot, normalized.get("derivatives"))
    flow = _build_dataclass(FlowSnapshot, normalized.get("flow"))
    context = _build_dataclass(ContextSnapshot, normalized.get("context"))

    return RegimeInputSnapshot(
        symbol=symbol,
        timestamp=engine_timestamp_ms,
        market=market,
        derivatives=derivatives,
        flow=flow,
        context=context,
    )


def _build_dataclass(cls: type, payload: Any) -> Any:
    values: dict[str, Any] = {}
    mapping: Mapping[str, Any] | None = payload if isinstance(payload, Mapping) else None
    for field in fields(cls):
        if mapping is None or field.name not in mapping:
            values[field.name] = MISSING
        else:
            values[field.name] = mapping[field.name]
    return cls(**values)
