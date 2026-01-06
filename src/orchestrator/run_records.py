from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from orchestrator.contracts import EngineRunRecord


@dataclass
class EngineRunLog:
    records: list[EngineRunRecord]

    def __init__(self) -> None:
        self.records = []

    def append(self, record: EngineRunRecord) -> None:
        self.records.append(record)

    def all_records(self) -> Iterable[EngineRunRecord]:
        return tuple(self.records)
