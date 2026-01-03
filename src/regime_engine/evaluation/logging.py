from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.evaluation.records import LogRecord, TransitionRecord, record_id_for
from regime_engine.hysteresis.decision import HysteresisDecision


def log_path(*, base_dir: str, timestamp: int) -> str:
    date_str = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(base_dir, f"{date_str}.jsonl")


def build_log_record(
    truth: RegimeOutput,
    decision: HysteresisDecision,
) -> LogRecord | None:
    if truth.symbol != decision.selected_output.symbol:
        return None

    transition = decision.transition
    transition_record = TransitionRecord(
        stable_regime=transition.stable_regime.value if transition.stable_regime else None,
        candidate_regime=transition.candidate_regime.value if transition.candidate_regime else None,
        candidate_count=transition.candidate_count,
        transition_active=transition.transition_active,
        flipped=transition.flipped,
        reset_due_to_gap=transition.reset_due_to_gap,
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
        selected_regime=decision.selected_output.regime.value,
        effective_confidence=decision.effective_confidence,
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
    decision: HysteresisDecision,
    *,
    base_dir: str = "logs/regime",
) -> bool:
    record = build_log_record(truth, decision)
    if record is None:
        return False
    append_record(record, base_dir=base_dir)
    return True
