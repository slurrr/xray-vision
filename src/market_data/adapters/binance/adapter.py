from __future__ import annotations

import asyncio
import json
import time
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass

import websockets

from market_data.adapter import AdapterSupervisor, StreamKey
from market_data.config import RetryPolicy
from market_data.contracts import RawMarketEvent
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline
from market_data.sink import BackpressureError

from .config import (
    BinanceAggTradeConfig,
    BinanceBookTickerConfig,
    BinanceDepthConfig,
    BinanceForceOrderConfig,
    BinanceKlineConfig,
    BinanceMarkPriceConfig,
    BinanceOpenInterestConfig,
)
from .decoder import (
    DecodedEvent,
    DecodedEvents,
    DecodeError,
    decode_agg_trade,
    decode_book_ticker,
    decode_depth,
    decode_force_order,
    decode_kline,
    decode_mark_price,
    decode_open_interest,
)


@dataclass(frozen=True)
class _AdapterConfig:
    source_id: str
    symbol: str
    stream: str
    channel: str
    ws_url: str
    retry: RetryPolicy
    connect_timeout_ms: int
    read_timeout_ms: int


class _BinanceWsAdapter:
    stream_key: StreamKey

    def __init__(
        self,
        *,
        config: _AdapterConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        self._config = config
        self._pipeline = pipeline
        self._observability = observability or Observability(
            logger=NullLogger(), metrics=NullMetrics()
        )
        self.stream_key = StreamKey(
            source_id=config.source_id,
            channel=config.channel,
            symbol=config.symbol,
        )
        self._supervisor = AdapterSupervisor(self.stream_key, config.retry)
        self._running = False

    def start(self) -> None:
        self._running = True

    def run(self) -> None:
        self._supervisor.record_start()
        while self._running:
            try:
                asyncio.run(self._consume_stream())
            except BackpressureError as exc:
                self._supervisor.record_failure(exc)
                self._observability.log_transport_state(
                    stream_key=self.stream_key,
                    state="backpressure",
                    reconnect_count=self._supervisor.status.failure_count,
                    error=str(exc),
                )
                self.stop()
                return
            except Exception as exc:
                self._supervisor.record_failure(exc)
                self._observability.log_transport_state(
                    stream_key=self.stream_key,
                    state="failed",
                    reconnect_count=self._supervisor.status.failure_count,
                    error=str(exc),
                )
                delay_ms = self._supervisor.next_retry_delay_ms()
                if delay_ms is None:
                    self.stop()
                    return
                time.sleep(delay_ms / 1000)
        self._supervisor.record_stop()

    def stop(self) -> None:
        self._running = False

    async def _consume_stream(self) -> None:
        url = f"{self._config.ws_url}/{self._config.stream}"
        self._observability.log_transport_state(
            stream_key=self.stream_key,
            state="connecting",
            reconnect_count=self._supervisor.status.failure_count,
        )
        async with websockets.connect(
            url,
            open_timeout=self._config.connect_timeout_ms / 1000,
            ping_interval=None,
            close_timeout=1,
        ) as websocket:
            self._observability.log_transport_state(
                stream_key=self.stream_key,
                state="connected",
                reconnect_count=self._supervisor.status.failure_count,
            )
            self._observability.record_connection_state(
                stream_key=self.stream_key,
                state="connected",
                reconnect_count=self._supervisor.status.failure_count,
            )
            while self._running:
                try:
                    message = await asyncio.wait_for(
                        websocket.recv(), timeout=self._config.read_timeout_ms / 1000
                    )
                except asyncio.TimeoutError as exc:
                    raise RuntimeError("read timeout") from exc
                self._handle_message(message)

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        raise NotImplementedError

    def _handle_message(self, message: str | bytes) -> None:
        raw_payload: str | bytes = message
        try:
            text = message if isinstance(message, str) else message.decode("utf-8")
            data = json.loads(text)
        except Exception as exc:
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind="decode_error",
                error_detail=str(exc),
            )
            return
        if not isinstance(data, Mapping):
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind="schema_mismatch",
                error_detail="payload is not a mapping",
            )
            return
        try:
            decoded = self._decode(data)
        except DecodeError as exc:
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind=exc.error_kind,
                error_detail=exc.error_detail,
            )
            return

        for error in decoded.errors:
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind=error.error_kind,
                error_detail=error.error_detail,
            )
        for event in decoded.events:
            self._emit_event(raw_payload=raw_payload, event=event)

    def _emit_event(self, *, raw_payload: str | bytes, event: DecodedEvent) -> None:
        self._pipeline.ingest(
            event_type=event.event_type,
            source_id=self._config.source_id,
            symbol=self._config.symbol,
            exchange_ts_ms=event.exchange_ts_ms,
            raw_payload=raw_payload,
            normalized=event.normalized,
            source_event_id=event.source_event_id,
            source_seq=event.source_seq,
            channel=self._config.channel,
        )

    def _emit_decode_failure(
        self,
        *,
        raw_payload: str | bytes,
        error_kind: str,
        error_detail: str,
    ) -> RawMarketEvent:
        return self._pipeline.ingest(
            event_type="DecodeFailure",
            source_id=self._config.source_id,
            symbol=self._config.symbol,
            exchange_ts_ms=None,
            raw_payload=raw_payload,
            normalized={"error_kind": error_kind, "error_detail": error_detail},
            channel=self._config.channel,
        )


class BinanceAggTradeAdapter(_BinanceWsAdapter):
    def __init__(
        self,
        *,
        config: BinanceAggTradeConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            config=_AdapterConfig(
                source_id=config.source_id,
                symbol=config.symbol,
                stream=config.stream,
                channel=config.channel,
                ws_url=config.ws_url,
                retry=config.retry,
                connect_timeout_ms=config.connect_timeout_ms,
                read_timeout_ms=config.read_timeout_ms,
            ),
            pipeline=pipeline,
            observability=observability,
        )

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        return DecodedEvents(events=(decode_agg_trade(payload),), errors=())


class BinanceKlineAdapter(_BinanceWsAdapter):
    def __init__(
        self,
        *,
        config: BinanceKlineConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            config=_AdapterConfig(
                source_id=config.source_id,
                symbol=config.symbol,
                stream=config.stream,
                channel=config.channel,
                ws_url=config.ws_url,
                retry=config.retry,
                connect_timeout_ms=config.connect_timeout_ms,
                read_timeout_ms=config.read_timeout_ms,
            ),
            pipeline=pipeline,
            observability=observability,
        )

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        return DecodedEvents(events=(decode_kline(payload),), errors=())


class BinanceBookTickerAdapter(_BinanceWsAdapter):
    def __init__(
        self,
        *,
        config: BinanceBookTickerConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            config=_AdapterConfig(
                source_id=config.source_id,
                symbol=config.symbol,
                stream=config.stream,
                channel=config.channel,
                ws_url=config.ws_url,
                retry=config.retry,
                connect_timeout_ms=config.connect_timeout_ms,
                read_timeout_ms=config.read_timeout_ms,
            ),
            pipeline=pipeline,
            observability=observability,
        )

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        return DecodedEvents(events=(decode_book_ticker(payload),), errors=())


class BinanceDepthAdapter(_BinanceWsAdapter):
    def __init__(
        self,
        *,
        config: BinanceDepthConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            config=_AdapterConfig(
                source_id=config.source_id,
                symbol=config.symbol,
                stream=config.stream,
                channel=config.channel,
                ws_url=config.ws_url,
                retry=config.retry,
                connect_timeout_ms=config.connect_timeout_ms,
                read_timeout_ms=config.read_timeout_ms,
            ),
            pipeline=pipeline,
            observability=observability,
        )

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        return DecodedEvents(events=(decode_depth(payload),), errors=())


class BinanceMarkPriceAdapter(_BinanceWsAdapter):
    def __init__(
        self,
        *,
        config: BinanceMarkPriceConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            config=_AdapterConfig(
                source_id=config.source_id,
                symbol=config.symbol,
                stream=config.stream,
                channel=config.channel,
                ws_url=config.ws_url,
                retry=config.retry,
                connect_timeout_ms=config.connect_timeout_ms,
                read_timeout_ms=config.read_timeout_ms,
            ),
            pipeline=pipeline,
            observability=observability,
        )

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        return decode_mark_price(payload)


class BinanceForceOrderAdapter(_BinanceWsAdapter):
    def __init__(
        self,
        *,
        config: BinanceForceOrderConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        super().__init__(
            config=_AdapterConfig(
                source_id=config.source_id,
                symbol=config.symbol,
                stream=config.stream,
                channel=config.channel,
                ws_url=config.ws_url,
                retry=config.retry,
                connect_timeout_ms=config.connect_timeout_ms,
                read_timeout_ms=config.read_timeout_ms,
            ),
            pipeline=pipeline,
            observability=observability,
        )

    def _decode(self, payload: Mapping[str, object]) -> DecodedEvents:
        return DecodedEvents(events=(decode_force_order(payload),), errors=())


class BinanceOpenInterestPoller:
    stream_key: StreamKey

    def __init__(
        self,
        *,
        config: BinanceOpenInterestConfig,
        pipeline: IngestionPipeline,
        observability: Observability | None = None,
    ) -> None:
        self._config = config
        self._pipeline = pipeline
        self._observability = observability or Observability(
            logger=NullLogger(), metrics=NullMetrics()
        )
        self.stream_key = StreamKey(
            source_id=config.source_id,
            channel=config.channel,
            symbol=config.symbol,
        )
        self._supervisor = AdapterSupervisor(self.stream_key, config.retry)
        self._running = False

    def start(self) -> None:
        self._running = True

    def run(self) -> None:
        self._supervisor.record_start()
        next_poll = time.monotonic()
        while self._running:
            now = time.monotonic()
            if now < next_poll:
                time.sleep(next_poll - now)
            try:
                self._poll_once()
            except BackpressureError as exc:
                self._supervisor.record_failure(exc)
                self._observability.log_transport_state(
                    stream_key=self.stream_key,
                    state="backpressure",
                    reconnect_count=self._supervisor.status.failure_count,
                    error=str(exc),
                )
                self.stop()
                return
            except Exception as exc:
                self._supervisor.record_failure(exc)
                self._observability.log_transport_state(
                    stream_key=self.stream_key,
                    state="failed",
                    reconnect_count=self._supervisor.status.failure_count,
                    error=str(exc),
                )
                delay_ms = self._supervisor.next_retry_delay_ms()
                if delay_ms is None:
                    self.stop()
                    return
                time.sleep(delay_ms / 1000)
            else:
                next_poll += self._config.poll_interval_ms / 1000
        self._supervisor.record_stop()

    def stop(self) -> None:
        self._running = False

    def _poll_once(self) -> None:
        url = f"{self._config.rest_url}/fapi/v1/openInterest?symbol={self._config.symbol}"
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(
            request, timeout=self._config.request_timeout_ms / 1000
        ) as response:
            raw_payload = response.read()
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except Exception as exc:
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind="decode_error",
                error_detail=str(exc),
            )
            return
        if not isinstance(payload, Mapping):
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind="schema_mismatch",
                error_detail="payload is not a mapping",
            )
            return
        try:
            decoded = decode_open_interest(payload)
        except DecodeError as exc:
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind=exc.error_kind,
                error_detail=exc.error_detail,
            )
            return
        self._pipeline.ingest(
            event_type=decoded.event_type,
            source_id=self._config.source_id,
            symbol=self._config.symbol,
            exchange_ts_ms=decoded.exchange_ts_ms,
            raw_payload=raw_payload,
            normalized=decoded.normalized,
            channel=self._config.channel,
        )

    def _emit_decode_failure(
        self,
        *,
        raw_payload: bytes | str,
        error_kind: str,
        error_detail: str,
    ) -> RawMarketEvent:
        return self._pipeline.ingest(
            event_type="DecodeFailure",
            source_id=self._config.source_id,
            symbol=self._config.symbol,
            exchange_ts_ms=None,
            raw_payload=raw_payload,
            normalized={"error_kind": error_kind, "error_detail": error_detail},
            channel=self._config.channel,
        )
