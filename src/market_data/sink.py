from __future__ import annotations

from typing import Protocol

from market_data.contracts import RawMarketEvent


class BackpressureError(RuntimeError):
    """Raised when the sink cannot accept additional events."""


class RawEventSink(Protocol):
    def write(self, event: RawMarketEvent, *, block: bool, timeout_ms: int | None) -> None:
        """Write a raw market event or raise BackpressureError when saturated."""
