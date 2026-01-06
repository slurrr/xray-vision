from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SymbolSequencer:
    last_timestamp_by_symbol: dict[str, int]

    def __init__(self) -> None:
        self.last_timestamp_by_symbol = {}

    def ensure_next(self, *, symbol: str, engine_timestamp_ms: int) -> None:
        last = self.last_timestamp_by_symbol.get(symbol)
        if last is not None and engine_timestamp_ms < last:
            raise ValueError("engine_timestamp_ms must be monotonic per symbol")
        self.last_timestamp_by_symbol[symbol] = engine_timestamp_ms
