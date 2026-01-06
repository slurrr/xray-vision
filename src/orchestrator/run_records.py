from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from orchestrator.contracts import EngineRunRecord


@dataclass
class EngineRunLog:
    records: List[EngineRunRecord]

    def __init__(self) -> None:
        self.records = []

    def append(self, record: EngineRunRecord) -> None:
        self.records.append(record)

    def all_records(self) -> Iterable[EngineRunRecord]:
        return tuple(self.records)
