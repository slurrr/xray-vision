from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass

from market_data.contracts import RawMarketEvent
from orchestrator.contracts import RawInputBufferRecord


class BufferFullError(RuntimeError):
    """Raised when the input buffer reaches configured capacity."""


@dataclass
class RawInputBuffer:
    max_records: int
    records: list[RawInputBufferRecord]
    _next_seq: int = 1

    def __init__(self, *, max_records: int) -> None:
        if max_records <= 0:
            raise ValueError("max_records must be > 0")
        self.max_records = max_records
        self.records = []
        self._next_seq = 1

    def append(
        self, event: RawMarketEvent, *, ingest_ts_ms: int | None = None
    ) -> RawInputBufferRecord:
        if len(self.records) >= self.max_records:
            raise BufferFullError("input buffer capacity exceeded")
        timestamp = ingest_ts_ms if ingest_ts_ms is not None else _now_ms()
        record = RawInputBufferRecord(
            ingest_seq=self._next_seq,
            ingest_ts_ms=timestamp,
            event=event,
        )
        self.records.append(record)
        self._next_seq += 1
        return record

    def all_records(self) -> Iterable[RawInputBufferRecord]:
        return tuple(self.records)

    def range_by_seq(self, *, start_seq: int, end_seq: int) -> list[RawInputBufferRecord]:
        if start_seq > end_seq:
            raise ValueError("start_seq must be <= end_seq")
        return [
            record
            for record in self.records
            if start_seq <= record.ingest_seq <= end_seq
        ]

    def range_by_symbol(
        self, *, symbol: str, start_seq: int, end_seq: int
    ) -> list[RawInputBufferRecord]:
        records = self.range_by_seq(start_seq=start_seq, end_seq=end_seq)
        return [record for record in records if record.event.symbol == symbol]

    def last_ingest_seq(self) -> int | None:
        if not self.records:
            return None
        return self.records[-1].ingest_seq

    def drop_through(self, *, end_seq: int) -> int:
        if not self.records:
            return 0
        kept: list[RawInputBufferRecord] = []
        dropped = 0
        for record in self.records:
            if record.ingest_seq <= end_seq:
                dropped += 1
            else:
                kept.append(record)
        self.records = kept
        return dropped


def _now_ms() -> int:
    return int(time.time() * 1000)
