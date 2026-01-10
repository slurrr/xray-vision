from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from market_data.config import BackpressureConfig
from market_data.contracts import (
    EVENT_TYPE_REQUIRED_NORMALIZED_KEYS,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    RawMarketEvent,
)
from market_data.observability import Observability, get_observability
from market_data.sink import BackpressureError, RawEventSink

ClockMs = Callable[[], int]


def _default_clock_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class IngestionPipeline:
    sink: RawEventSink
    backpressure: BackpressureConfig
    observability: Observability
    clock_ms: ClockMs = _default_clock_ms

    def ingest(
        self,
        *,
        event_type: str,
        source_id: str,
        symbol: str,
        exchange_ts_ms: int | None,
        raw_payload: bytes | str,
        normalized: Mapping[str, object],
        source_event_id: str | None = None,
        source_seq: int | None = None,
        channel: str | None = None,
        payload_content_type: str | None = None,
        payload_hash: str | None = None,
    ) -> RawMarketEvent:
        recv_ts_ms = self.clock_ms()
        _validate_event_type(event_type)
        _validate_required_normalized_keys(event_type, normalized)

        event = RawMarketEvent(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            event_type=event_type,
            source_id=source_id,
            symbol=symbol,
            exchange_ts_ms=exchange_ts_ms,
            recv_ts_ms=recv_ts_ms,
            raw_payload=raw_payload,
            normalized=normalized,
            source_event_id=source_event_id,
            source_seq=source_seq,
            channel=channel,
            payload_content_type=payload_content_type,
            payload_hash=payload_hash,
        )

        self._emit(event)
        return event

    def _emit(self, event: RawMarketEvent) -> None:
        block = self.backpressure.policy == "block"
        timeout_ms = self.backpressure.max_block_ms if block else 0
        start = time.monotonic()
        try:
            self.sink.write(event, block=block, timeout_ms=timeout_ms)
        except BackpressureError:
            blocked_ms = int((time.monotonic() - start) * 1000)
            self.observability.record_backpressure(blocked_ms, source_id=event.source_id)
            raise
        else:
            blocked_ms = int((time.monotonic() - start) * 1000)
            if block and blocked_ms > 0:
                self.observability.record_backpressure(blocked_ms, source_id=event.source_id)
            self.observability.record_event(event)


def _validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPE_REQUIRED_NORMALIZED_KEYS:
        raise ValueError(f"unsupported event_type: {event_type}")


def _validate_required_normalized_keys(event_type: str, normalized: Mapping[str, object]) -> None:
    required_keys = EVENT_TYPE_REQUIRED_NORMALIZED_KEYS[event_type]
    missing = required_keys.difference(normalized.keys())
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"missing normalized keys for {event_type}: {missing_list}")


def emit_cadence_summary(symbol: str) -> None:
    get_observability().log_cadence_summary(symbol=symbol)
