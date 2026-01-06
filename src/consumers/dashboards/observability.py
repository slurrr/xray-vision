from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .contracts import DashboardViewModel


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


@dataclass
class Observability:
    logger: StructuredLogger
    metrics: MetricsRecorder

    def log_snapshot(self, snapshot: DashboardViewModel, *, latency_ms: int | None = None) -> None:
        fields: dict[str, object] = {
            "dvm_schema": snapshot.dvm_schema,
            "dvm_schema_version": snapshot.dvm_schema_version,
            "as_of_ts_ms": snapshot.as_of_ts_ms,
            "source_run_id": snapshot.source_run_id,
            "source_engine_timestamp_ms": snapshot.source_engine_timestamp_ms,
        }
        if latency_ms is not None:
            fields["production_latency_ms"] = latency_ms
        self.logger.log(logging.INFO, "dashboards.snapshot_produced", fields)

    def record_snapshot_metrics(
        self, *, latency_ms: int | None = None, builder_lag_ms: int | None = None
    ) -> None:
        self.metrics.increment("dashboards.snapshots.produced")
        if latency_ms is not None:
            self.metrics.observe("dashboards.snapshot_latency_ms", float(latency_ms))
        if builder_lag_ms is not None:
            self.metrics.gauge("dashboards.builder.lag_ms", float(builder_lag_ms))

    def log_ingest_failure(
        self,
        *,
        input_schema: str,
        input_event_type: str | None,
        error_kind: str,
        error_detail: str,
    ) -> None:
        fields: dict[str, object] = {
            "input_schema": input_schema,
            "input_event_type": input_event_type,
            "error_kind": error_kind,
            "error_detail": error_detail,
        }
        self.logger.log(logging.ERROR, "dashboards.ingest_failure", fields)
        self.metrics.increment(
            "dashboards.failures", tags={"component": "builder", "error_kind": error_kind}
        )

    def log_renderer_failure(self, *, error_kind: str, error_detail: str) -> None:
        fields: dict[str, object] = {
            "error_kind": error_kind,
            "error_detail": error_detail,
        }
        self.logger.log(logging.ERROR, "dashboards.renderer_failure", fields)
        self.metrics.increment(
            "dashboards.failures", tags={"component": "renderer", "error_kind": error_kind}
        )

    def record_renderer_frame(self) -> None:
        self.metrics.increment("dashboards.renderer.frames")
