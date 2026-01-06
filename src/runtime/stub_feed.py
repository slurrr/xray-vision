from __future__ import annotations

import json
import time
from collections.abc import Callable

from market_data.config import BackpressureConfig
from market_data.contracts import RawMarketEvent
from market_data.observability import NullLogger, NullMetrics, Observability
from market_data.pipeline import IngestionPipeline
from market_data.sink import RawEventSink
from runtime.bus import EventBus

ClockMs = Callable[[], int]


class BusRawEventSink(RawEventSink):
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def write(self, event: RawMarketEvent, *, block: bool, timeout_ms: int | None) -> None:
        self._bus.publish(event)


class StubMarketDataFeed:
    def __init__(
        self,
        *,
        bus: EventBus,
        source_id: str,
        symbol: str,
        interval_ms: int,
        clock_ms: ClockMs | None = None,
    ) -> None:
        self._source_id = source_id
        self._symbol = symbol
        self._interval_ms = interval_ms
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._pipeline = IngestionPipeline(
            sink=BusRawEventSink(bus),
            backpressure=BackpressureConfig(policy="fail", max_pending=10_000),
            observability=Observability(logger=NullLogger(), metrics=NullMetrics()),
            clock_ms=self._clock_ms,
        )

    def run(self) -> None:
        while True:
            timestamp_ms = self._clock_ms()
            payload = _snapshot_payload(timestamp_ms)
            raw_payload = json.dumps(payload, separators=(",", ":"))
            self._pipeline.ingest(
                event_type="SnapshotInputs",
                source_id=self._source_id,
                symbol=self._symbol,
                exchange_ts_ms=timestamp_ms,
                raw_payload=raw_payload,
                normalized=payload,
                channel="stub",
                payload_content_type="application/json",
            )
            time.sleep(self._interval_ms / 1000)


def _snapshot_payload(timestamp_ms: int) -> dict[str, object]:
    return {
        "timestamp_ms": timestamp_ms,
        "market": {
            "price": 100.0,
            "vwap": 100.0,
            "atr": 1.0,
            "atr_z": 0.1,
            "range_expansion": 0.2,
            "structure_levels": {},
            "acceptance_score": 0.5,
            "sweep_score": 0.1,
        },
        "derivatives": {
            "open_interest": 1000.0,
            "oi_slope_short": 0.0,
            "oi_slope_med": 0.0,
            "oi_accel": 0.0,
            "funding_rate": 0.0,
            "funding_slope": 0.0,
            "funding_z": 0.0,
            "liquidation_intensity": None,
        },
        "flow": {
            "cvd": 0.0,
            "cvd_slope": 0.0,
            "cvd_efficiency": 0.0,
            "aggressive_volume_ratio": 0.5,
        },
        "context": {
            "rs_vs_btc": 0.0,
            "beta_to_btc": 1.0,
            "alt_breadth": 0.0,
            "btc_regime": None,
            "eth_regime": None,
        },
    }
