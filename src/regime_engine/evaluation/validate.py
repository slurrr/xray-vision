from __future__ import annotations

from typing import Any

from regime_engine.contracts.regimes import Regime
from regime_engine.evaluation.records import LogRecord, TransitionRecord, record_id_for

_VALID_REGIMES = {regime.value for regime in Regime}


def _as_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    return None


def _as_str(value: object) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _as_str_list(value: object) -> list[str] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return list(value)


def parse_record(data: dict[str, Any]) -> LogRecord | None:
    schema_version = _as_int(data.get("schema_version"))
    if schema_version != 1:
        return None

    symbol = _as_str(data.get("symbol"))
    timestamp = _as_int(data.get("timestamp"))
    record_id = _as_str(data.get("record_id"))
    truth_regime = _as_str(data.get("truth_regime"))
    truth_confidence = _as_float(data.get("truth_confidence"))
    drivers = _as_str_list(data.get("drivers"))
    invalidations = _as_str_list(data.get("invalidations"))
    permissions = _as_str_list(data.get("permissions"))
    selected_regime = _as_str(data.get("selected_regime"))
    effective_confidence = _as_float(data.get("effective_confidence"))
    transition = data.get("transition")

    if symbol is None:
        return None
    if timestamp is None:
        return None
    if record_id is None:
        return None
    if truth_regime is None:
        return None
    if truth_confidence is None:
        return None
    if drivers is None:
        return None
    if invalidations is None:
        return None
    if permissions is None:
        return None
    if selected_regime is None:
        return None
    if effective_confidence is None:
        return None

    if truth_regime not in _VALID_REGIMES or selected_regime not in _VALID_REGIMES:
        return None

    if record_id != record_id_for(symbol, timestamp):
        return None

    if not isinstance(transition, dict):
        return None

    stable_regime = _as_str(transition.get("stable_regime"))
    candidate_regime = _as_str(transition.get("candidate_regime"))
    candidate_count = _as_int(transition.get("candidate_count"))
    transition_active = _as_bool(transition.get("transition_active"))
    flipped = _as_bool(transition.get("flipped"))
    reset_due_to_gap = _as_bool(transition.get("reset_due_to_gap"))

    if candidate_count is None:
        return None
    if transition_active is None:
        return None
    if flipped is None:
        return None
    if reset_due_to_gap is None:
        return None

    if stable_regime is not None and stable_regime not in _VALID_REGIMES:
        return None
    if candidate_regime is not None and candidate_regime not in _VALID_REGIMES:
        return None

    transition_record = TransitionRecord(
        stable_regime=stable_regime,
        candidate_regime=candidate_regime,
        candidate_count=candidate_count,
        transition_active=transition_active,
        flipped=flipped,
        reset_due_to_gap=reset_due_to_gap,
    )

    return LogRecord(
        schema_version=schema_version,
        record_id=record_id,
        symbol=symbol,
        timestamp=timestamp,
        truth_regime=truth_regime,
        truth_confidence=truth_confidence,
        drivers=drivers,
        invalidations=invalidations,
        permissions=permissions,
        selected_regime=selected_regime,
        effective_confidence=effective_confidence,
        transition=transition_record,
    )
