from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.evaluation.records import LogRecord, TransitionRecord, record_id_for
from regime_engine.hysteresis.state import HysteresisState


def log_path(*, base_dir: str, timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
    date_str = dt.strftime("%Y-%m-%d")
    return os.path.join(base_dir, f"{date_str}.jsonl")


def build_log_record(
    truth: RegimeOutput,
    hysteresis_state: HysteresisState,
) -> LogRecord | None:
    if truth.symbol != hysteresis_state.symbol:
        return None

    transition_active = hysteresis_state.progress_current > 0
    flipped = any(code.startswith("COMMIT_SWITCH:") for code in hysteresis_state.reason_codes)
    transition_record = TransitionRecord(
        stable_regime=hysteresis_state.anchor_regime.value,
        candidate_regime=hysteresis_state.candidate_regime.value
        if hysteresis_state.candidate_regime
        else None,
        candidate_count=hysteresis_state.progress_current,
        transition_active=transition_active,
        flipped=flipped,
        reset_due_to_gap=False,
    )

    return LogRecord(
        schema_version=1,
        record_id=record_id_for(truth.symbol, truth.timestamp),
        symbol=truth.symbol,
        timestamp=truth.timestamp,
        truth_regime=truth.regime.value,
        truth_confidence=truth.confidence,
        drivers=list(truth.drivers),
        invalidations=list(truth.invalidations),
        permissions=list(truth.permissions),
        selected_regime=hysteresis_state.anchor_regime.value,
        effective_confidence=truth.confidence,
        transition=transition_record,
    )


def append_record(record: LogRecord, *, base_dir: str = "logs/regime") -> str:
    path = log_path(base_dir=base_dir, timestamp=record.timestamp)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")))
        handle.write("\n")
    return path


def log_update(
    truth: RegimeOutput,
    hysteresis_state: HysteresisState,
    *,
    base_dir: str = "logs/regime",
) -> bool:
    record = build_log_record(truth, hysteresis_state)
    if record is None:
        return False
    append_record(record, base_dir=base_dir)
    return True
