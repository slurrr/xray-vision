from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from market_data.contracts import RawMarketEvent
from orchestrator.contracts import EngineRunRecord, OrchestratorEvent
from orchestrator.failure_handling import BackpressureState
from orchestrator.lifecycle import Lifecycle, OrchestratorState


class StructuredLogger(Protocol):
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None: ...


class MetricsRecorder(Protocol):
    def increment(
        self, name: str, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None: ...

    def observe(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None: ...

    def gauge(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None: ...


@dataclass(frozen=True)
class StdlibLogger:
    logger: logging.Logger

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.logger.log(level, message, extra={"fields": dict(fields)})


@dataclass(frozen=True)
class NullLogger:
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        return None


@dataclass(frozen=True)
class NullMetrics:
    def increment(
        self, name: str, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:
        return None

    def observe(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:
        return None

    def gauge(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:
        return None


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    state: str
    ingestion_paused: bool
    scheduling_paused: bool


@dataclass(frozen=True)
class Observability:
    logger: StructuredLogger
    metrics: MetricsRecorder

    def log_ingest(self, event: RawMarketEvent, *, ingest_seq: int) -> None:
        self.logger.log(
            logging.INFO,
            "orchestrator.ingest",
            {
                "source_id": event.source_id,
                "symbol": event.symbol,
                "ingest_seq": ingest_seq,
                "recv_ts_ms": event.recv_ts_ms,
                "exchange_ts_ms": event.exchange_ts_ms,
            },
        )

    def log_run(self, record: EngineRunRecord, *, attempt: int) -> None:
        self.logger.log(
            logging.INFO,
            "orchestrator.engine_run",
            {
                "run_id": record.run_id,
                "symbol": record.symbol,
                "engine_timestamp_ms": record.engine_timestamp_ms,
                "cut_start_ingest_seq": record.cut_start_ingest_seq,
                "cut_end_ingest_seq": record.cut_end_ingest_seq,
                "engine_mode": record.engine_mode,
                "attempt": attempt,
            },
        )

    def log_engine_invocation(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        embedded_evidence_present: bool,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "orchestrator.engine.invoke",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "embedded_evidence_present": embedded_evidence_present,
            },
        )

    def log_failure(
        self,
        *,
        domain: str,
        error_kind: str,
        error_detail: str,
        run_record: EngineRunRecord | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "failure_domain": domain,
            "error_kind": error_kind,
            "error_detail": error_detail,
        }
        if run_record is not None:
            fields.update(
                {
                    "run_id": run_record.run_id,
                    "symbol": run_record.symbol,
                    "engine_timestamp_ms": run_record.engine_timestamp_ms,
                    "cut_start_ingest_seq": run_record.cut_start_ingest_seq,
                    "cut_end_ingest_seq": run_record.cut_end_ingest_seq,
                    "engine_mode": run_record.engine_mode,
                    "attempt": run_record.attempts,
                }
            )
        self.logger.log(logging.WARNING, "orchestrator.failure", fields)

    def record_ingest_metrics(self, event: RawMarketEvent) -> None:
        self.metrics.increment(
            "orchestrator.ingest.count",
            tags={"source_id": event.source_id, "event_type": event.event_type},
        )

    def record_buffer_metrics(self, *, depth: int, age_ms: int) -> None:
        self.metrics.gauge("orchestrator.buffer.depth", float(depth))
        self.metrics.gauge("orchestrator.buffer.age_ms", float(age_ms))

    def record_scheduler_tick(self, *, lag_ms: int) -> None:
        self.metrics.increment("orchestrator.scheduler.ticks")
        self.metrics.observe("orchestrator.scheduler.lag_ms", float(lag_ms))

    def record_engine_metrics(self, *, duration_ms: int, success: bool) -> None:
        self.metrics.increment(
            "orchestrator.engine.runs",
            tags={"status": "success" if success else "failure"},
        )
        self.metrics.observe("orchestrator.engine.duration_ms", float(duration_ms))

    def record_publish_metrics(self, event: OrchestratorEvent) -> None:
        self.metrics.increment(
            "orchestrator.publish.count",
            tags={"event_type": event.event_type},
        )

    def record_publish_latency(self, latency_ms: int) -> None:
        self.metrics.observe("orchestrator.publish.latency_ms", float(latency_ms))

    def record_backpressure(self, *, domain: str, blocked_ms: int) -> None:
        self.metrics.increment("orchestrator.backpressure.count", tags={"domain": domain})
        self.metrics.observe(
            "orchestrator.backpressure.blocked_ms",
            float(blocked_ms),
            tags={"domain": domain},
        )


def compute_health(lifecycle: Lifecycle, backpressure: BackpressureState) -> HealthStatus:
    ready = lifecycle.state == OrchestratorState.RUNNING and not (
        backpressure.ingestion_paused or backpressure.scheduling_paused
    )
    return HealthStatus(
        ready=ready,
        state=str(lifecycle.state.value),
        ingestion_paused=backpressure.ingestion_paused,
        scheduling_paused=backpressure.scheduling_paused,
    )
