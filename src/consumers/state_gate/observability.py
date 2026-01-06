from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .contracts import StateGateEvent, StateResetPayload


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


@dataclass(frozen=True)
class HealthStatus:
    ready: bool
    halted: bool
    input_healthy: bool
    persistence_healthy: bool
    publish_healthy: bool


@dataclass
class Observability:
    logger: StructuredLogger
    metrics: MetricsRecorder

    def log_event(self, event: StateGateEvent) -> None:
        fields: dict[str, object] = {
            "symbol": event.symbol,
            "run_id": event.run_id,
            "engine_timestamp_ms": event.engine_timestamp_ms,
            "input_event_type": event.input_event_type,
            "state_status": event.state_status,
            "gate_status": event.gate_status,
            "reasons": list(event.reasons),
        }
        if event.event_type == "StateReset" and isinstance(event.payload, StateResetPayload):
            fields["reset_reason"] = event.payload.reset_reason
        if event.event_type == "StateGateHalted":
            fields["error_kind"] = getattr(event.payload, "error_kind", None)
            fields["error_detail"] = getattr(event.payload, "error_detail", None)
        self.logger.log(
            logging.INFO,
            f"state_gate.{event.event_type}",
            fields,
        )

    def record_metrics(
        self, event: StateGateEvent, *, processing_lag_ms: int | None = None
    ) -> None:
        if event.event_type == "StateReset":
            reset_reason = (
                event.payload.reset_reason
                if isinstance(event.payload, StateResetPayload)
                else "unknown"
            )
            self.metrics.increment("state_gate.resets", tags={"reset_reason": reset_reason})
            self.metrics.increment(
                "state_gate.transitions", tags={"state_status": event.state_status}
            )
            return None

        if event.event_type == "StateGateHalted":
            error_kind = (
                getattr(event.payload, "error_kind", "internal_failure")
                if event.payload
                else "internal_failure"
            )
            self.metrics.increment("state_gate.failures", tags={"error_kind": str(error_kind)})
            self.metrics.gauge("state_gate.halted", 1.0)
            self.metrics.increment(
                "state_gate.transitions", tags={"state_status": event.state_status}
            )
            return None

        if event.event_type != "GateEvaluated":
            return None

        reasons = list(event.reasons) or ["none"]
        for reason in reasons:
            self.metrics.increment(
                "state_gate.gate_decisions",
                tags={"gate_status": event.gate_status, "reason": reason},
            )
        self.metrics.increment(
            "state_gate.transitions", tags={"state_status": event.state_status}
        )
        if processing_lag_ms is not None:
            self.metrics.observe(
                "state_gate.processing_lag_ms",
                float(processing_lag_ms),
                tags={"symbol": event.symbol},
            )
