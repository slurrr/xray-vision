from __future__ import annotations

from market_data.contracts import RawMarketEvent
from market_data.sink import RawEventSink
from runtime.bus import EventBus


class BusRawEventSink(RawEventSink):
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    def write(self, event: RawMarketEvent, *, block: bool, timeout_ms: int | None) -> None:
        self._bus.publish(event)
