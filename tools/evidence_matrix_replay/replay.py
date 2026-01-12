from __future__ import annotations

import argparse
import base64
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any, cast

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.contracts import (
    ENGINE_MODE_HYSTERESIS,
    ENGINE_MODE_TRUTH,
    EngineRunRecord,
    OrchestratorEvent,
)
from orchestrator.engine_runner import EngineRunResult
from orchestrator.replay import replay_events
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.engine import run
from regime_engine.hysteresis import (
    HysteresisConfig,
    HysteresisState,
    HysteresisStore,
    process_state,
)
from regime_engine.hysteresis.persistence import restore_store
from regime_engine.pipeline import run_pipeline_with_state

_RAW_EVENTS_FILENAME = "raw_market_events.jsonl"
_ORCH_EVENTS_FILENAME = "orchestrator_events.jsonl"
_REGIME_OUTPUTS_FILENAME = "regime_outputs.jsonl"
_HYSTERESIS_STATES_FILENAME = "hysteresis_states.jsonl"
_PERSISTENCE_COUNTS_FILENAME = "persistence_counts.json"


@dataclass(frozen=True)
class ReplayInputs:
    raw_events: tuple[RawMarketEvent, ...]
    run_records: tuple[EngineRunRecord, ...]


class ReplayEngineRunner:
    def __init__(
        self,
        *,
        engine_mode: str,
        hysteresis_store: HysteresisStore | None,
        hysteresis_config: HysteresisConfig | None,
    ) -> None:
        self.engine_mode = engine_mode
        self.hysteresis_store = hysteresis_store
        self.hysteresis_config = hysteresis_config
        self.append_count_total = 0
        self.append_count_by_symbol: dict[str, int] = {}

    def run(self, snapshot: RegimeInputSnapshot) -> RegimeOutput | EngineRunResult:
        if self.engine_mode == ENGINE_MODE_TRUTH:
            return run(snapshot)
        if self.engine_mode == ENGINE_MODE_HYSTERESIS:
            store = self.hysteresis_store
            if store is None:
                raise ValueError("hysteresis_store is required for hysteresis mode")
            _guard_monotonic(store, snapshot)
            output, regime_state = run_pipeline_with_state(snapshot)
            prev_state = store.state_for(snapshot.symbol)
            hysteresis_state = process_state(
                regime_state,
                store=store,
                config=self.hysteresis_config,
            )
            if _state_advanced(prev_state, hysteresis_state):
                self.append_count_total += 1
                self.append_count_by_symbol[snapshot.symbol] = (
                    self.append_count_by_symbol.get(snapshot.symbol, 0) + 1
                )
            return EngineRunResult(
                regime_output=output,
                hysteresis_state=hysteresis_state,
            )
        raise ValueError("unsupported engine_mode")


def _guard_monotonic(store: HysteresisStore, snapshot: RegimeInputSnapshot) -> None:
    symbol = snapshot.symbol
    prev_state = store.state_for(symbol)
    if prev_state is None:
        return
    if snapshot.timestamp < prev_state.engine_timestamp_ms:
        raise ValueError("hysteresis monotonicity violation")


def _state_advanced(
    prev_state: HysteresisState | None,
    next_state: HysteresisState,
) -> bool:
    if prev_state is None:
        return True
    return (
        prev_state.anchor_regime != next_state.anchor_regime
        or prev_state.candidate_regime != next_state.candidate_regime
        or prev_state.progress_current != next_state.progress_current
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay captured events deterministically.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
        help="Directory containing capture artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write replay outputs (default: <input-dir>/replay_outputs).",
    )
    parser.add_argument(
        "--hysteresis-state-path",
        type=Path,
        default=None,
        help="Optional hysteresis store file for hysteresis mode.",
    )
    return parser.parse_args()

def _ensure_output_dir_is_new(output_dir: str) -> None:
    path = Path(output_dir)
    if path.exists():
        raise SystemExit(
            f"ERROR: Output directory already exists:\n"
            f"  {path}\n\n"
            f"Replay outputs are write-once. "
            f"Choose a new --output-dir."
        )
    path.mkdir(parents=True, exist_ok=False)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _write_jsonl(path: Path, items: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, separators=(",", ":"), sort_keys=True))
            handle.write("\n")


def _decode_raw_payload(value: object, encoding: str) -> bytes | str:
    if encoding == "base64":
        if not isinstance(value, str):
            raise ValueError("raw_payload must be base64 string")
        return base64.b64decode(value)
    if not isinstance(value, str):
        raise ValueError("raw_payload must be text")
    return value


def _load_raw_events(path: Path) -> tuple[RawMarketEvent, ...]:
    raw_items = _load_jsonl(path)
    events: list[RawMarketEvent] = []
    for item in raw_items:
        payload_encoding = item.get("raw_payload_encoding", "text")
        raw_payload = _decode_raw_payload(item.get("raw_payload"), payload_encoding)
        events.append(
            RawMarketEvent(
                schema=item["schema"],
                schema_version=item["schema_version"],
                event_type=item["event_type"],
                source_id=item["source_id"],
                symbol=item["symbol"],
                exchange_ts_ms=item.get("exchange_ts_ms"),
                recv_ts_ms=item["recv_ts_ms"],
                raw_payload=raw_payload,
                normalized=item["normalized"],
                source_event_id=item.get("source_event_id"),
                source_seq=item.get("source_seq"),
                channel=item.get("channel"),
                payload_content_type=item.get("payload_content_type"),
                payload_hash=item.get("payload_hash"),
            )
        )
    return tuple(events)


def _load_run_records(path: Path) -> tuple[EngineRunRecord, ...]:
    events = _load_jsonl(path)
    started: list[dict[str, Any]] = []
    status_by_run: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = event["event_type"]
        run_id = event["run_id"]
        if event_type == "EngineRunStarted":
            started.append(event)
            status_by_run.setdefault(run_id, {})
        elif event_type == "EngineRunFailed":
            status_by_run[run_id] = {
                "status": "failed",
                "error_kind": (event.get("payload") or {}).get("error_kind"),
                "error_detail": (event.get("payload") or {}).get("error_detail"),
            }
        elif event_type == "EngineRunCompleted":
            status_by_run[run_id] = {"status": "completed"}
    run_records: list[EngineRunRecord] = []
    for entry in started:
        run_id = entry["run_id"]
        status_entry = status_by_run.get(run_id)
        if status_entry is None or "status" not in status_entry:
            raise ValueError(f"missing terminal status for run_id={run_id}")
        attempts = entry.get("attempt") or 1
        engine_mode = entry.get("engine_mode")
        if engine_mode is None:
            raise ValueError(f"missing engine_mode for run_id={run_id}")
        run_records.append(
            EngineRunRecord(
                run_id=run_id,
                symbol=entry["symbol"],
                engine_timestamp_ms=entry["engine_timestamp_ms"],
                engine_mode=engine_mode,
                cut_kind=entry["cut_kind"],
                cut_start_ingest_seq=entry["cut_start_ingest_seq"],
                cut_end_ingest_seq=entry["cut_end_ingest_seq"],
                planned_ts_ms=entry["engine_timestamp_ms"],
                started_ts_ms=None,
                completed_ts_ms=None,
                status=status_entry["status"],
                attempts=attempts,
                error_kind=status_entry.get("error_kind"),
                error_detail=status_entry.get("error_detail"),
            )
        )
    return tuple(run_records)


def _validate_run_records(
    run_records: Sequence[EngineRunRecord], *, total_events: int
) -> None:
    if not run_records:
        raise ValueError("no run records available")
    modes = {record.engine_mode for record in run_records}
    if len(modes) != 1:
        raise ValueError("mixed engine modes not supported in replay harness")
    for record in run_records:
        if record.cut_start_ingest_seq < 1 or record.cut_end_ingest_seq < 1:
            raise ValueError("cut ingest sequences must be >= 1")
        if record.cut_start_ingest_seq > record.cut_end_ingest_seq:
            raise ValueError("cut_start_ingest_seq must be <= cut_end_ingest_seq")
        if record.cut_end_ingest_seq > total_events:
            raise ValueError("cut_end_ingest_seq exceeds captured events")


def _reconstruct_buffer(events: Sequence[RawMarketEvent]) -> RawInputBuffer:
    buffer = RawInputBuffer(max_records=max(1, len(events)))
    for event in events:
        buffer.append(event, ingest_ts_ms=event.recv_ts_ms)
    return buffer


def _validate_buffer(buffer: RawInputBuffer, run_records: Iterable[EngineRunRecord]) -> None:
    for record in run_records:
        records = buffer.range_by_seq(
            start_seq=record.cut_start_ingest_seq,
            end_seq=record.cut_end_ingest_seq,
        )
        expected = record.cut_end_ingest_seq - record.cut_start_ingest_seq + 1
        if len(records) != expected:
            raise ValueError("captured raw events do not cover run cut range")


def _load_inputs(input_dir: Path) -> ReplayInputs:
    raw_path = input_dir / _RAW_EVENTS_FILENAME
    orch_path = input_dir / _ORCH_EVENTS_FILENAME
    raw_events = _load_raw_events(raw_path)
    run_records = _load_run_records(orch_path)
    _validate_run_records(run_records, total_events=len(raw_events))
    buffer = _reconstruct_buffer(raw_events)
    _validate_buffer(buffer, run_records)
    return ReplayInputs(raw_events=raw_events, run_records=run_records)


def _build_engine_runner(
    *,
    mode: str,
    hysteresis_state_path: Path | None,
) -> ReplayEngineRunner:
    hysteresis_store = None
    hysteresis_config = None
    if mode == ENGINE_MODE_HYSTERESIS:
        if hysteresis_state_path is not None:
            hysteresis_store = restore_store(
                path=str(hysteresis_state_path),
                config=HysteresisConfig(),
            )
        else:
            hysteresis_store = HysteresisStore(states={})
        hysteresis_config = HysteresisConfig()
    return ReplayEngineRunner(
        engine_mode=mode,
        hysteresis_store=hysteresis_store,
        hysteresis_config=hysteresis_config,
    )


def _serialize_payload(payload: object) -> object:
    if isinstance(payload, Regime):
        return payload.value
    if is_dataclass(payload):
        return _serialize_dataclass(payload)
    if isinstance(payload, dict):
        return {key: _serialize_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_serialize_payload(value) for value in payload]
    if isinstance(payload, tuple):
        return [_serialize_payload(value) for value in payload]
    return payload


def _serialize_dataclass(payload: object) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in fields(cast(Any, payload)):
        value = getattr(payload, field.name)
        result[field.name] = _serialize_payload(value)
    return result


def _capture_outputs(
    events: Sequence[OrchestratorEvent],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    regime_outputs: list[dict[str, Any]] = []
    hysteresis_states: list[dict[str, Any]] = []
    for event in events:
        if event.event_type == "EngineRunCompleted":
            payload = event.payload
            if payload is not None:
                regime_output = cast(Any, payload).regime_output
                regime_outputs.append(cast(dict[str, Any], _serialize_payload(regime_output)))
        elif event.event_type == "HysteresisStatePublished":
            payload = event.payload
            if payload is not None:
                hysteresis_state = cast(Any, payload).hysteresis_state
                hysteresis_states.append(
                    cast(dict[str, Any], _serialize_payload(hysteresis_state))
                )
    return regime_outputs, hysteresis_states


def main() -> None:
    args = _parse_args()
    _ensure_output_dir_is_new(args.output_dir)
    inputs = _load_inputs(args.input_dir)
    buffer = _reconstruct_buffer(inputs.raw_events)
    mode = inputs.run_records[0].engine_mode
    runner = _build_engine_runner(
        mode=mode,
        hysteresis_state_path=args.hysteresis_state_path,
    )
    result = replay_events(
        buffer=buffer,
        run_records=inputs.run_records,
        engine_runner=runner.run,
    )
    output_dir = args.output_dir or (args.input_dir / "replay_outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    regime_outputs, hysteresis_states = _capture_outputs(result.events)
    _write_jsonl(output_dir / _REGIME_OUTPUTS_FILENAME, regime_outputs)
    _write_jsonl(output_dir / _HYSTERESIS_STATES_FILENAME, hysteresis_states)
    persistence_counts = {
        "total": runner.append_count_total,
        "by_symbol": runner.append_count_by_symbol,
    }
    (output_dir / _PERSISTENCE_COUNTS_FILENAME).write_text(
        json.dumps(persistence_counts, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "replayed_events": len(result.events),
                "regime_outputs": len(regime_outputs),
                "hysteresis_states": len(hysteresis_states),
                "persistence_appends": runner.append_count_total,
                "output_dir": str(output_dir),
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
