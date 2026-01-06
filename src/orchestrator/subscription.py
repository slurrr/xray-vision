from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from market_data.contracts import RawMarketEvent
from orchestrator.buffer import RawInputBuffer


class InputSubscriber(Protocol):
    def start(self, handler: Callable[[RawMarketEvent], None]) -> None: ...

    def stop(self) -> None: ...


@dataclass
class BufferingSubscriber:
    buffer: RawInputBuffer

    def handle_event(self, event: RawMarketEvent) -> None:
        self.buffer.append(event)
