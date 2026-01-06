from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Protocol

from market_data.adapter import StreamKey
from market_data.contracts import RawMarketEvent


class StructuredLogger(Protocol):
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None: ...


class MetricsRecorder(Protocol):
    def increment(self, name: str, value: int = 1, tags: Mapping[str, str] | None = None) -> None: ...

    def observe(self, name: str, value: float, tags: Mapping[str, str] | None = None) -> None: ...

    def gauge(self, name: str, value: float, tags: Mapping[str, str] | None = None) -> None: ...


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
    def increment(self, name: str, value: int = 1, tags: Mapping[str, str] | None = None) -> None:
        return None

    def observe(self, name: str, value: float, tags: Mapping[str, str] | None = None) -> None:
        return None

    def gauge(self, name: str, value: float, tags: Mapping[str, str] | None = None) -> None:
        return None


@dataclass(frozen=True)
class Observability:
    logger: StructuredLogger
    metrics: MetricsRecorder

    def record_event(self, event: RawMarketEvent) -> None:
        if event.event_type == "DecodeFailure":
            self.log_decode_failure(event)
            self.record_decode_failure_metrics(event)
        else:
            self.log_event(event)
            self.record_event_metrics(event)
        self.record_latency_metrics(event)

    def log_event(self, event: RawMarketEvent) -> None:
        self.logger.log(
            logging.INFO,
            "market_data.event",
            {
                "source_id": event.source_id,
                "symbol": event.symbol,
                "event_type": event.event_type,
                "exchange_ts_ms": event.exchange_ts_ms,
                "recv_ts_ms": event.recv_ts_ms,
            },
        )

    def log_decode_failure(self, event: RawMarketEvent) -> None:
        self.logger.log(
            logging.WARNING,
            "market_data.decode_failure",
            {
                "source_id": event.source_id,
                "symbol": event.symbol,
                "event_type": event.event_type,
                "exchange_ts_ms": event.exchange_ts_ms,
                "recv_ts_ms": event.recv_ts_ms,
                "error_kind": event.normalized.get("error_kind"),
                "error_detail": event.normalized.get("error_detail"),
            },
        )

    def log_transport_state(
        self,
        *,
        stream_key: StreamKey,
        state: str,
        reconnect_count: int | None = None,
        error: str | None = None,
    ) -> None:
        fields: dict[str, object] = {
            "source_id": stream_key.source_id,
            "symbol": stream_key.symbol,
            "channel": stream_key.channel,
            "state": state,
        }
        if reconnect_count is not None:
            fields["reconnect_count"] = reconnect_count
        if error is not None:
            fields["error_detail"] = error
        self.logger.log(logging.INFO, "market_data.transport_state", fields)

    def record_event_metrics(self, event: RawMarketEvent) -> None:
        self.metrics.increment(
            "market_data.events.count",
            tags={"source_id": event.source_id, "event_type": event.event_type},
        )

    def record_decode_failure_metrics(self, event: RawMarketEvent) -> None:
        error_kind = event.normalized.get("error_kind")
        self.metrics.increment(
            "market_data.decode_failures.count",
            tags={"source_id": event.source_id, "error_kind": str(error_kind)},
        )

    def record_latency_metrics(self, event: RawMarketEvent) -> None:
        if event.exchange_ts_ms is None:
            return
        latency_ms = event.recv_ts_ms - event.exchange_ts_ms
        self.metrics.observe(
            "market_data.exchange_to_recv.latency_ms",
            float(latency_ms),
            tags={"source_id": event.source_id, "event_type": event.event_type},
        )

    def record_backpressure(self, blocked_ms: int, *, source_id: str) -> None:
        self.metrics.increment(
            "market_data.backpressure.count",
            tags={"source_id": source_id},
        )
        self.metrics.observe(
            "market_data.backpressure.blocked_ms",
            float(blocked_ms),
            tags={"source_id": source_id},
        )

    def record_connection_state(
        self, *, stream_key: StreamKey, state: str, reconnect_count: int
    ) -> None:
        self.metrics.gauge(
            "market_data.transport.state",
            1.0,
            tags={
                "source_id": stream_key.source_id,
                "channel": stream_key.channel,
                "symbol": str(stream_key.symbol),
                "state": state,
            },
        )
        self.metrics.increment(
            "market_data.transport.reconnects",
            tags={
                "source_id": stream_key.source_id,
                "channel": stream_key.channel,
                "symbol": str(stream_key.symbol),
            },
            value=reconnect_count,
        )
