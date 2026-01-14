from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from composer.engine_evidence.compute import compute_engine_evidence_snapshot
from composer.evidence.compute import compute_evidence_snapshot
from composer.features.compute import compute_feature_snapshot
from composer.legacy_snapshot import build_legacy_snapshot
from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer
from orchestrator.contracts import ENGINE_MODE_HYSTERESIS, EngineRunRecord, OrchestratorEvent
from orchestrator.engine_runner import EngineRunResult
from orchestrator.publisher import (
    build_engine_run_completed,
    build_engine_run_failed,
    build_engine_run_started,
    build_hysteresis_state_published,
)
from orchestrator.sequencing import SymbolSequencer
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.hysteresis.state import HysteresisState

EngineCallable = Callable[[RegimeInputSnapshot], RegimeOutput | EngineRunResult]


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
        raw_events = _raw_events_for_cut(
            buffer=buffer,
            symbol=record.symbol,
            start_seq=record.cut_start_ingest_seq,
            end_seq=record.cut_end_ingest_seq,
        )
        counts_by_event_type = _counts_by_event_type(raw_events)
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
                counts_by_event_type=counts_by_event_type,
            )
            _publish(sequencer, events, failure_event)
            continue

        try:
            feature_snapshot = compute_feature_snapshot(
                raw_events,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
            )
            evidence_snapshot = compute_engine_evidence_snapshot(feature_snapshot)
            neutral_evidence_snapshot = compute_evidence_snapshot(feature_snapshot)
            snapshot = build_legacy_snapshot(
                raw_events,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
                feature_snapshot=feature_snapshot,
                evidence_snapshot=evidence_snapshot,
                neutral_evidence_snapshot=neutral_evidence_snapshot,
            )
        except Exception as exc:
            failure_event = build_engine_run_failed(
                run_id=record.run_id,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
                cut_start_ingest_seq=record.cut_start_ingest_seq,
                cut_end_ingest_seq=record.cut_end_ingest_seq,
                cut_kind=record.cut_kind,
                engine_mode=record.engine_mode,
                error_kind="snapshot_build_failure",
                error_detail=str(exc),
                attempt=record.attempts,
                counts_by_event_type=counts_by_event_type,
            )
            _publish(sequencer, events, failure_event)
            continue

        output = engine_runner(snapshot)
        if record.engine_mode == ENGINE_MODE_HYSTERESIS:
            if not isinstance(output, EngineRunResult):
                raise ValueError("expected EngineRunResult for hysteresis mode")
            regime_output = output.regime_output
            hysteresis_state = output.hysteresis_state
            if not isinstance(hysteresis_state, HysteresisState):
                raise ValueError("expected HysteresisState for hysteresis mode")
            decision_event = build_hysteresis_state_published(
                run_id=record.run_id,
                symbol=record.symbol,
                engine_timestamp_ms=record.engine_timestamp_ms,
                cut_start_ingest_seq=record.cut_start_ingest_seq,
                cut_end_ingest_seq=record.cut_end_ingest_seq,
                cut_kind=record.cut_kind,
                hysteresis_state=hysteresis_state,
                attempt=record.attempts,
                counts_by_event_type=counts_by_event_type,
            )
            _publish(sequencer, events, decision_event)
            completed_output = regime_output
        else:
            if isinstance(output, EngineRunResult):
                completed_output = output.regime_output
            elif isinstance(output, RegimeOutput):
                completed_output = output
            else:
                raise ValueError("expected RegimeOutput for truth mode")

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
            counts_by_event_type=counts_by_event_type,
        )
        _publish(sequencer, events, completed_event)

    return ReplayResult(events=events)


def _publish(
    sequencer: SymbolSequencer, events: list[OrchestratorEvent], event: OrchestratorEvent
) -> None:
    sequencer.ensure_next(symbol=event.symbol, engine_timestamp_ms=event.engine_timestamp_ms)
    events.append(event)


def _raw_events_for_cut(
    *,
    buffer: RawInputBuffer,
    symbol: str,
    start_seq: int,
    end_seq: int,
) -> tuple[RawMarketEvent, ...]:
    records = buffer.range_by_symbol(symbol=symbol, start_seq=start_seq, end_seq=end_seq)
    return tuple(record.event for record in records)


def _counts_by_event_type(raw_events: tuple[RawMarketEvent, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in raw_events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    return counts
