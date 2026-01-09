from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .contracts import AnalysisEngineEvent, ArtifactEmittedPayload, ModuleFailedPayload


class StructuredLogger(Protocol):
    def log(
        self, level: int, message: str, fields: Mapping[str, object]
    ) -> None: ...  # pragma: no cover


class MetricsRecorder(Protocol):
    def increment(
        self, name: str, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None: ...  # pragma: no cover

    def observe(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None: ...  # pragma: no cover

    def gauge(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None: ...  # pragma: no cover


@dataclass(frozen=True)
class NullLogger:
    def log(
        self, level: int, message: str, fields: Mapping[str, object]
    ) -> None:  # pragma: no cover - stub
        return None


@dataclass(frozen=True)
class StdlibLogger:
    logger: logging.Logger

    def log(
        self, level: int, message: str, fields: Mapping[str, object]
    ) -> None:  # pragma: no cover - passthrough
        self.logger.log(level, message, extra={"fields": dict(fields)})




@dataclass(frozen=True)
class NullMetrics:
    def increment(
        self, name: str, value: int = 1, tags: Mapping[str, str] | None = None
    ) -> None:  # pragma: no cover - stub
        return None

    def observe(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:  # pragma: no cover - stub
        return None

    def gauge(
        self, name: str, value: float, tags: Mapping[str, str] | None = None
    ) -> None:  # pragma: no cover - stub
        return None


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    halted: bool
    registry_loaded: bool
    idempotency_available: bool


@dataclass
class Observability:
    logger: StructuredLogger
    metrics: MetricsRecorder
    registry_loaded: bool = True
    halted: bool = False

    def log_event(self, event: AnalysisEngineEvent) -> None:
        fields: dict[str, object] = {
            "symbol": event.symbol,
            "run_id": event.run_id,
            "engine_timestamp_ms": event.engine_timestamp_ms,
            "event_type": event.event_type,
        }
        if event.engine_mode is not None:
            fields["engine_mode"] = event.engine_mode
        if isinstance(event.payload, ArtifactEmittedPayload):
            fields.update(
                {
                    "module_id": event.payload.module_id,
                    "module_kind": event.payload.artifact_kind,
                    "artifact_name": event.payload.artifact_name,
                }
            )
        if isinstance(event.payload, ModuleFailedPayload):
            fields.update(
                {
                    "module_id": event.payload.module_id,
                    "module_kind": event.payload.module_kind,
                    "error_kind": event.payload.error_kind,
                    "error_detail": event.payload.error_detail,
                }
            )
        self.logger.log(logging.INFO, "analysis_engine.event", fields)

    def record_metrics(self, event: AnalysisEngineEvent) -> None:
        if isinstance(event.payload, ArtifactEmittedPayload):
            self.metrics.increment(
                "analysis_engine.artifacts",
                tags={
                    "module_id": event.payload.module_id,
                    "artifact_kind": event.payload.artifact_kind,
                },
            )
        if isinstance(event.payload, ModuleFailedPayload):
            self.metrics.increment(
                "analysis_engine.module_failures",
                tags={"module_id": event.payload.module_id, "error_kind": event.payload.error_kind},
            )
        if event.event_type == "AnalysisRunCompleted" and hasattr(event.payload, "status"):
            status = getattr(event.payload, "status", "UNKNOWN")
            self.metrics.increment("analysis_engine.run_status", tags={"status": str(status)})
        if event.event_type == "AnalysisRunSkipped":
            self.metrics.increment(
                "analysis_engine.idempotency_skips", tags={"reason": "gate_closed"}
            )

    def record_idempotency_skip(self) -> None:
        self.metrics.increment(
            "analysis_engine.idempotency_skips", tags={"reason": "duplicate_run_id"}
        )

    def mark_halted(self) -> None:
        self.halted = True

    def health_status(self) -> HealthStatus:
        ready = self.registry_loaded and not self.halted
        return HealthStatus(
            ready=ready,
            halted=self.halted,
            registry_loaded=self.registry_loaded,
            idempotency_available=True,
        )
