from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

EventT = TypeVar("EventT")


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable[[object], None]]] = {}

    def subscribe(self, event_type: type[EventT], handler: Callable[[EventT], None]) -> None:
        handlers = self._handlers.setdefault(event_type, [])
        handlers.append(cast(Callable[[object], None], handler))

    def publish(self, event: object) -> None:
        handlers: list[Callable[[object], None]] = []
        for event_type, registered in self._handlers.items():
            if isinstance(event, event_type):
                handlers.extend(registered)
        for handler in handlers:
            handler(event)
