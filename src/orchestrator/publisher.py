from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from orchestrator.contracts import (
    ENGINE_MODE_HYSTERESIS,
    ENGINE_MODE_TRUTH,
    EngineRunCompletedPayload,
    EngineRunFailedPayload,
    HysteresisDecisionPayload,
    OrchestratorEvent,
    SCHEMA_NAME,
    SCHEMA_VERSION,
)
from orchestrator.sequencing import SymbolSequencer
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.hysteresis.decision import HysteresisDecision


class EventSink(Protocol):
    def write(self, event: OrchestratorEvent) -> None: ...


@dataclass
class OrchestratorEventPublisher:
    sink: EventSink
    sequencer: SymbolSequencer

    def publish(self, event: OrchestratorEvent) -> None:
        self.sequencer.ensure_next(symbol=event.symbol, engine_timestamp_ms=event.engine_timestamp_ms)
        self.sink.write(event)


def build_engine_run_started(
    *,
    run_id: str,
    symbol: str,
    engine_timestamp_ms: int,
    cut_start_ingest_seq: int,
    cut_end_ingest_seq: int,
    cut_kind: str,
    engine_mode: str,
    attempt: int | None = None,
    published_ts_ms: int | None = None,
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="EngineRunStarted",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=cut_start_ingest_seq,
        cut_end_ingest_seq=cut_end_ingest_seq,
        cut_kind=cut_kind,
        engine_mode=engine_mode,
        attempt=attempt,
        published_ts_ms=published_ts_ms,
    )


def build_engine_run_completed(
    *,
    run_id: str,
    symbol: str,
    engine_timestamp_ms: int,
    cut_start_ingest_seq: int,
    cut_end_ingest_seq: int,
    cut_kind: str,
    engine_mode: str,
    regime_output: RegimeOutput,
    attempt: int | None = None,
    published_ts_ms: int | None = None,
    counts_by_event_type: Mapping[str, int] | None = None,
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="EngineRunCompleted",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=cut_start_ingest_seq,
        cut_end_ingest_seq=cut_end_ingest_seq,
        cut_kind=cut_kind,
        engine_mode=engine_mode,
        attempt=attempt,
        published_ts_ms=published_ts_ms,
        counts_by_event_type=counts_by_event_type,
        payload=EngineRunCompletedPayload(regime_output=regime_output),
    )


def build_engine_run_failed(
    *,
    run_id: str,
    symbol: str,
    engine_timestamp_ms: int,
    cut_start_ingest_seq: int,
    cut_end_ingest_seq: int,
    cut_kind: str,
    engine_mode: str,
    error_kind: str,
    error_detail: str,
    attempt: int | None = None,
    published_ts_ms: int | None = None,
    counts_by_event_type: Mapping[str, int] | None = None,
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="EngineRunFailed",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=cut_start_ingest_seq,
        cut_end_ingest_seq=cut_end_ingest_seq,
        cut_kind=cut_kind,
        engine_mode=engine_mode,
        attempt=attempt,
        published_ts_ms=published_ts_ms,
        counts_by_event_type=counts_by_event_type,
        payload=EngineRunFailedPayload(error_kind=error_kind, error_detail=error_detail),
    )


def build_hysteresis_decision_published(
    *,
    run_id: str,
    symbol: str,
    engine_timestamp_ms: int,
    cut_start_ingest_seq: int,
    cut_end_ingest_seq: int,
    cut_kind: str,
    hysteresis_decision: HysteresisDecision,
    attempt: int | None = None,
    published_ts_ms: int | None = None,
    counts_by_event_type: Mapping[str, int] | None = None,
) -> OrchestratorEvent:
    return OrchestratorEvent(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        event_type="HysteresisDecisionPublished",
        run_id=run_id,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        cut_start_ingest_seq=cut_start_ingest_seq,
        cut_end_ingest_seq=cut_end_ingest_seq,
        cut_kind=cut_kind,
        engine_mode=ENGINE_MODE_HYSTERESIS,
        attempt=attempt,
        published_ts_ms=published_ts_ms,
        counts_by_event_type=counts_by_event_type,
        payload=HysteresisDecisionPayload(hysteresis_decision=hysteresis_decision),
    )
