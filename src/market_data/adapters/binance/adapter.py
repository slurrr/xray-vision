from __future__ import annotations

import asyncio
import json
import time

import websockets

from market_data.adapter import AdapterSupervisor, StreamKey
from market_data.contracts import RawMarketEvent
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline

from .config import BinanceTradeAdapterConfig


class BinanceTradeAdapter:
    stream_key: StreamKey

    def __init__(
        self,
        *,
        config: BinanceTradeAdapterConfig,
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
            channel="trade",
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

    def _handle_message(self, message: str | bytes) -> None:
        raw_payload: str | bytes = message
        try:
            data = json.loads(message if isinstance(message, str) else message.decode("utf-8"))
            exchange_ts_ms = _require_int(data, "T")
            price = _require_float(data, "p")
            quantity = _require_float(data, "q")
            maker = _require_bool(data, "m")
            side = "sell" if maker else "buy"
        except Exception as exc:
            self._emit_decode_failure(
                raw_payload=raw_payload,
                error_kind="decode_error",
                error_detail=str(exc),
            )
            return

        self._pipeline.ingest(
            event_type="TradeTick",
            source_id=self._config.source_id,
            symbol=self._config.symbol,
            exchange_ts_ms=exchange_ts_ms,
            raw_payload=raw_payload,
            normalized={"price": price, "quantity": quantity, "side": side},
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
        )


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool):
        raise ValueError(f"invalid {key}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise ValueError(f"missing {key}")


def _require_float(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise ValueError(f"missing {key}")


def _require_bool(payload: dict[str, object], key: str) -> bool:
    value = payload.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
    raise ValueError(f"missing {key}")
