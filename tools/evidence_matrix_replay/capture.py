from __future__ import annotations

import argparse
import base64
import json
import threading
import time
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, cast

from consumers.analysis_engine.config.loader import (
    load_default_config as load_analysis_engine_config,
)
from consumers.dashboards.config.loader import load_default_config as load_dashboards_config
from consumers.state_gate.config.loader import load_default_config as load_state_gate_config
from market_data.config.loader import load_default_config as load_market_data_config
from market_data.contracts import RawMarketEvent
from market_data.runtime import build_market_data_runtime
from orchestrator.config.loader import load_default_config as load_orchestrator_config
from orchestrator.contracts import OrchestratorEvent
from regime_engine.contracts.regimes import Regime
from regime_engine.hysteresis.state import HysteresisState
from runtime.bus import EventBus
from runtime.bus_sink import BusRawEventSink
from runtime.observability import bootstrap_observability
from runtime.wiring import build_runtime, register_subscriptions

_RAW_EVENTS_FILENAME = "raw_market_events.jsonl"
_ORCH_EVENTS_FILENAME = "orchestrator_events.jsonl"


class JsonlWriter:
    def __init__(self, path: Path, *, overwrite: bool) -> None:
        self._lock = threading.Lock()
        mode = "w" if overwrite else "x"
        self._handle = path.open(mode, encoding="utf-8")

    def write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        with self._lock:
            self._handle.write(line)
            self._handle.write("\n")
            self._handle.flush()

    def close(self) -> None:
        with self._lock:
            self._handle.close()


def _serialize_raw_event(event: RawMarketEvent) -> dict[str, Any]:
    raw_payload, raw_payload_encoding = _encode_raw_payload(event.raw_payload)
    return {
        "schema": event.schema,
        "schema_version": event.schema_version,
        "event_type": event.event_type,
        "source_id": event.source_id,
        "symbol": event.symbol,
        "exchange_ts_ms": event.exchange_ts_ms,
        "recv_ts_ms": event.recv_ts_ms,
        "raw_payload": raw_payload,
        "raw_payload_encoding": raw_payload_encoding,
        "normalized": event.normalized,
        "source_event_id": event.source_event_id,
        "source_seq": event.source_seq,
        "channel": event.channel,
        "payload_content_type": event.payload_content_type,
        "payload_hash": event.payload_hash,
    }


def _serialize_orchestrator_event(event: OrchestratorEvent) -> dict[str, Any]:
    payload = None
    if event.payload is not None:
        payload = _serialize_payload(event.payload)
    return {
        "schema": event.schema,
        "schema_version": event.schema_version,
        "event_type": event.event_type,
        "run_id": event.run_id,
        "symbol": event.symbol,
        "engine_timestamp_ms": event.engine_timestamp_ms,
        "cut_start_ingest_seq": event.cut_start_ingest_seq,
        "cut_end_ingest_seq": event.cut_end_ingest_seq,
        "cut_kind": event.cut_kind,
        "engine_mode": event.engine_mode,
        "attempt": event.attempt,
        "published_ts_ms": event.published_ts_ms,
        "counts_by_event_type": event.counts_by_event_type,
        "payload": payload,
    }


def _encode_raw_payload(payload: bytes | str) -> tuple[str, str]:
    if isinstance(payload, bytes):
        encoded = base64.b64encode(payload).decode("ascii")
        return encoded, "base64"
    return payload, "text"


def _serialize_payload(payload: object) -> object:
    if isinstance(payload, Regime):
        return payload.value
    if isinstance(payload, HysteresisState):
        return _serialize_dataclass(payload)
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture runtime events for replay.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write capture artifacts.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing capture files.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=None,
        help="Optional duration to run before exiting.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / _RAW_EVENTS_FILENAME
    orch_path = output_dir / _ORCH_EVENTS_FILENAME
    raw_writer = JsonlWriter(raw_path, overwrite=args.overwrite)
    orch_writer = JsonlWriter(orch_path, overwrite=args.overwrite)

    def handle_raw_event(event: RawMarketEvent) -> None:
        try:
            raw_writer.write(_serialize_raw_event(event))
        except Exception:
            return None

    def handle_orchestrator_event(event: OrchestratorEvent) -> None:
        try:
            orch_writer.write(_serialize_orchestrator_event(event))
        except Exception:
            return None

    observability = bootstrap_observability(log_dir="logs")
    analysis_engine_config = load_analysis_engine_config()
    dashboards_config = load_dashboards_config()
    state_gate_config = load_state_gate_config()
    orchestrator_config = load_orchestrator_config()
    market_data_config = load_market_data_config()
    bus = EventBus()
    runtime = build_runtime(
        bus,
        orchestrator_config=orchestrator_config,
        state_gate_config=state_gate_config,
        analysis_engine_config=analysis_engine_config,
        dashboards_config=dashboards_config,
    )
    register_subscriptions(bus, runtime)
    bus.subscribe(RawMarketEvent, handle_raw_event)
    bus.subscribe(OrchestratorEvent, handle_orchestrator_event)

    market_data_runtime = build_market_data_runtime(
        sink=BusRawEventSink(bus),
        observability=observability.market_data,
        config=market_data_config,
    )
    runtime.orchestrator.start()
    runtime.dashboards.start()
    runtime.dashboards.render_once()
    observability.runtime.log_runtime_started()
    market_info = market_data_runtime.info
    observability.runtime.log_market_data_adapters_initialized(
        symbol=market_info.symbol,
        adapter_count=market_info.adapter_count,
        optional_enabled=market_info.optional_enabled,
    )
    market_data_runtime.start()
    try:
        if args.duration_seconds is None:
            while True:
                time.sleep(1)
        else:
            time.sleep(max(0, args.duration_seconds))
    finally:
        market_data_runtime.stop()
        runtime.orchestrator.stop()
        runtime.dashboards.stop()
        raw_writer.close()
        orch_writer.close()


if __name__ == "__main__":
    main()
