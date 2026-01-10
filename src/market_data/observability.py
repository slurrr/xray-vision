from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from market_data.adapter import StreamKey
from market_data.contracts import RawMarketEvent


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


@dataclass
class _SymbolCadenceStats:
    raw_events_ingested: int = 0
    decode_failures: int = 0
    first_event_timestamp_ms: int | None = None
    last_event_timestamp_ms: int | None = None

    def record(self, *, event_type: str, event_timestamp_ms: int) -> None:
        if event_type == "DecodeFailure":
            self.decode_failures += 1
        else:
            self.raw_events_ingested += 1
        if self.first_event_timestamp_ms is None:
            self.first_event_timestamp_ms = event_timestamp_ms
        self.last_event_timestamp_ms = event_timestamp_ms


@dataclass
class MarketDataHealthTracker:
    _symbol_stats: dict[str, _SymbolCadenceStats] = field(default_factory=dict)
    _adapter_states: dict[str, str] = field(default_factory=dict)

    def record_event(self, event: RawMarketEvent) -> None:
        symbol = event.symbol
        stats = self._symbol_stats.setdefault(symbol, _SymbolCadenceStats())
        event_timestamp_ms = event.exchange_ts_ms or event.recv_ts_ms
        stats.record(event_type=event.event_type, event_timestamp_ms=event_timestamp_ms)

    def record_transport_state(self, *, stream_key: StreamKey, state: str) -> None:
        self._adapter_states[_stream_key_id(stream_key)] = state

    def snapshot_and_reset(self, symbol: str) -> dict[str, object]:
        stats = self._symbol_stats.pop(symbol, _SymbolCadenceStats())
        adapter_status = _adapter_status_for_symbol(symbol, self._adapter_states)
        return {
            "raw_events_ingested": stats.raw_events_ingested,
            "decode_failures": stats.decode_failures,
            "first_event_timestamp_ms": stats.first_event_timestamp_ms,
            "last_event_timestamp_ms": stats.last_event_timestamp_ms,
            "adapter_status": adapter_status,
        }


def _stream_key_id(stream_key: StreamKey) -> str:
    symbol = stream_key.symbol or ""
    return f"{stream_key.source_id}:{stream_key.channel}:{symbol}"


def _adapter_status_for_symbol(
    symbol: str, adapter_states: Mapping[str, str]
) -> str:
    if not adapter_states:
        return "disconnected"
    target = f":{symbol}"
    for key, state in adapter_states.items():
        if key.endswith(target) and state == "connected":
            return "connected"
    return "disconnected"


@dataclass(frozen=True)
class Observability:
    logger: StructuredLogger
    metrics: MetricsRecorder
    health: MarketDataHealthTracker = field(default_factory=MarketDataHealthTracker)

    def record_event(self, event: RawMarketEvent) -> None:
        self.health.record_event(event)
        if event.event_type == "DecodeFailure":
            self.log_decode_failure(event)
            self.record_decode_failure_metrics(event)
        else:
            self.log_event(event)
            self.record_event_metrics(event)
        self.record_latency_metrics(event)

    def log_event(self, event: RawMarketEvent) -> None:
        self.logger.log(
            logging.DEBUG,
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
            logging.DEBUG,
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
        self.health.record_transport_state(stream_key=stream_key, state=state)
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

    def log_cadence_summary(self, *, symbol: str) -> None:
        fields = {
            "symbol": symbol,
            **self.health.snapshot_and_reset(symbol),
        }
        self.logger.log(logging.INFO, "market_data.cadence_summary", fields)


_OBSERVABILITY = Observability(logger=NullLogger(), metrics=NullMetrics())


def set_observability(observability: Observability) -> None:
    global _OBSERVABILITY
    _OBSERVABILITY = observability


def get_observability() -> Observability:
    return _OBSERVABILITY
