from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    HysteresisConfig,
    HysteresisState,
    HysteresisStore,
)

RECORD_SCHEMA = "hysteresis_store_record"
RECORD_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class HysteresisStoreRecord:
    symbol: str
    engine_timestamp_ms: int
    anchor_regime: Regime
    candidate_regime: Regime | None
    progress_current: int
    last_commit_timestamp_ms: int | None


def build_record(state: HysteresisState) -> HysteresisStoreRecord:
    return HysteresisStoreRecord(
        symbol=state.symbol,
        engine_timestamp_ms=state.engine_timestamp_ms,
        anchor_regime=state.anchor_regime,
        candidate_regime=state.candidate_regime,
        progress_current=state.progress_current,
        last_commit_timestamp_ms=state.last_commit_timestamp_ms,
    )


def serialize_record(record: HysteresisStoreRecord) -> dict[str, object]:
    return {
        "schema": RECORD_SCHEMA,
        "schema_version": RECORD_SCHEMA_VERSION,
        "symbol": record.symbol,
        "engine_timestamp_ms": record.engine_timestamp_ms,
        "anchor_regime": record.anchor_regime.value,
        "candidate_regime": record.candidate_regime.value if record.candidate_regime else None,
        "progress_current": record.progress_current,
        "last_commit_timestamp_ms": record.last_commit_timestamp_ms,
    }


def encode_record(record: HysteresisStoreRecord) -> str:
    payload = serialize_record(record)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def parse_record(data: Mapping[str, object]) -> HysteresisStoreRecord:
    if data.get("schema") != RECORD_SCHEMA or data.get("schema_version") != RECORD_SCHEMA_VERSION:
        raise ValueError("invalid record schema")
    symbol = data.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("record symbol must be non-empty")
    engine_timestamp_ms = _require_int(data.get("engine_timestamp_ms"), "engine_timestamp_ms")
    anchor_regime = _parse_regime(data.get("anchor_regime"), "anchor_regime")
    candidate_raw = data.get("candidate_regime")
    candidate_regime = None
    if candidate_raw is not None:
        candidate_regime = _parse_regime(candidate_raw, "candidate_regime")
    progress_current = _require_int(data.get("progress_current"), "progress_current")
    if progress_current < 0:
        raise ValueError("progress_current must be >= 0")
    last_commit_raw = data.get("last_commit_timestamp_ms")
    last_commit_timestamp_ms = None
    if last_commit_raw is not None:
        last_commit_timestamp_ms = _require_int(
            last_commit_raw, "last_commit_timestamp_ms"
        )
    return HysteresisStoreRecord(
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        anchor_regime=anchor_regime,
        candidate_regime=candidate_regime,
        progress_current=progress_current,
        last_commit_timestamp_ms=last_commit_timestamp_ms,
    )


def restore_store(
    *, path: str, config: HysteresisConfig
) -> HysteresisStore:
    if not os.path.exists(path):
        return HysteresisStore(states={})
    records = _load_records(path)
    if not records:
        raise ValueError("no valid hysteresis records found")
    _ensure_hysteresis_schema()
    states = {
        symbol: _restore_state(record, config=config) for symbol, record in records.items()
    }
    return HysteresisStore(states=states)


def append_record(path: str, state: HysteresisState) -> None:
    record = build_record(state)
    payload = encode_record(record)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load_records(path: str) -> dict[str, HysteresisStoreRecord]:
    records: dict[str, HysteresisStoreRecord] = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, Mapping):
                continue
            try:
                record = parse_record(parsed)
            except ValueError:
                continue
            existing = records.get(record.symbol)
            if existing is None or record.engine_timestamp_ms >= existing.engine_timestamp_ms:
                records[record.symbol] = record
    return records


def _restore_state(
    record: HysteresisStoreRecord, *, config: HysteresisConfig
) -> HysteresisState:
    return HysteresisState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=record.symbol,
        engine_timestamp_ms=record.engine_timestamp_ms,
        anchor_regime=record.anchor_regime,
        candidate_regime=record.candidate_regime,
        progress_current=record.progress_current,
        progress_required=config.window_updates,
        last_commit_timestamp_ms=record.last_commit_timestamp_ms,
        reason_codes=(),
        debug=None,
    )


def _ensure_hysteresis_schema() -> None:
    if SCHEMA_NAME != "hysteresis_state" or SCHEMA_VERSION != "1":
        raise RuntimeError("unsupported hysteresis state schema")


def _parse_regime(value: object, field_name: str) -> Regime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    for regime in Regime:
        if regime.value == value:
            return regime
    raise ValueError(f"unknown regime value for {field_name}")


def _require_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be int")
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value
