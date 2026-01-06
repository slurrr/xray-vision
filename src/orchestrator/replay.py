from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from orchestrator.buffer import RawInputBuffer
from orchestrator.contracts import ENGINE_MODE_HYSTERESIS, EngineRunRecord, OrchestratorEvent
from orchestrator.cuts import Cut
from orchestrator.publisher import (
    build_engine_run_completed,
    build_engine_run_failed,
    build_engine_run_started,
    build_hysteresis_decision_published,
)
from orchestrator.sequencing import SymbolSequencer
from orchestrator.snapshots import build_snapshot, select_snapshot_event
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decision import HysteresisDecision

EngineCallable = Callable[[object], object]


@dataclass
class ReplayResult:
    events: list[OrchestratorEvent]


def replay_events(
    *,
    buffer: RawInputBuffer,
    run_records: Iterable[EngineRunRecord],
    engine_runner: EngineCallable,
) -> ReplayResult:
    sequencer = SymbolSequencer()
    events: list[OrchestratorEvent] = []

    for record in run_records:
        start_event = build_engine_run_started(
            run_id=record.run_id,
            symbol=record.symbol,
            engine_timestamp_ms=record.engine_timestamp_ms,
            cut_start_ingest_seq=record.cut_start_ingest_seq,
            cut_end_ingest_seq=record.cut_end_ingest_seq,
            cut_kind=record.cut_kind,
            engine_mode=record.engine_mode,
            attempt=record.attempts,
        )
        _publish(sequencer, events, start_event)

        if record.status == "failed":
            failure_event = build_engine_run_failed(
                run_id=record.run_id,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
                cut_start_ingest_seq=record.cut_start_ingest_seq,
                cut_end_ingest_seq=record.cut_end_ingest_seq,
                cut_kind=record.cut_kind,
                engine_mode=record.engine_mode,
                error_kind=record.error_kind or "engine_failure",
                error_detail=record.error_detail or "engine failure",
                attempt=record.attempts,
            )
            _publish(sequencer, events, failure_event)
            continue

        cut = Cut(
            symbol=record.symbol,
            cut_start_ingest_seq=record.cut_start_ingest_seq,
            cut_end_ingest_seq=record.cut_end_ingest_seq,
            cut_kind=record.cut_kind,
        )
        snapshot_event = select_snapshot_event(
            buffer=buffer, cut=cut, engine_timestamp_ms=record.engine_timestamp_ms
        )
        if snapshot_event is None:
            failure_event = build_engine_run_failed(
                run_id=record.run_id,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
                cut_start_ingest_seq=record.cut_start_ingest_seq,
                cut_end_ingest_seq=record.cut_end_ingest_seq,
                cut_kind=record.cut_kind,
                engine_mode=record.engine_mode,
                error_kind="missing_snapshot_inputs",
                error_detail="missing SnapshotInputs",
                attempt=record.attempts,
            )
            _publish(sequencer, events, failure_event)
            continue

        snapshot = build_snapshot(
            symbol=record.symbol,
            engine_timestamp_ms=record.engine_timestamp_ms,
            snapshot_event=snapshot_event,
        )
        output = engine_runner(snapshot)
        if record.engine_mode == ENGINE_MODE_HYSTERESIS:
            if not isinstance(output, HysteresisDecision):
                raise ValueError("expected HysteresisDecision for hysteresis mode")
            decision_event = build_hysteresis_decision_published(
                run_id=record.run_id,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
                cut_start_ingest_seq=record.cut_start_ingest_seq,
                cut_end_ingest_seq=record.cut_end_ingest_seq,
                cut_kind=record.cut_kind,
                hysteresis_decision=output,
                attempt=record.attempts,
            )
            _publish(sequencer, events, decision_event)
            completed_output = output.selected_output
        else:
            if not isinstance(output, RegimeOutput):
                raise ValueError("expected RegimeOutput for truth mode")
            completed_output = output

        completed_event = build_engine_run_completed(
            run_id=record.run_id,
            symbol=record.symbol,
            engine_timestamp_ms=record.engine_timestamp_ms,
            cut_start_ingest_seq=record.cut_start_ingest_seq,
            cut_end_ingest_seq=record.cut_end_ingest_seq,
            cut_kind=record.cut_kind,
            engine_mode=record.engine_mode,
            regime_output=completed_output,
            attempt=record.attempts,
        )
        _publish(sequencer, events, completed_event)

    return ReplayResult(events=events)


def _publish(
    sequencer: SymbolSequencer, events: list[OrchestratorEvent], event: OrchestratorEvent
) -> None:
    sequencer.ensure_next(symbol=event.symbol, engine_timestamp_ms=event.engine_timestamp_ms)
    events.append(event)
