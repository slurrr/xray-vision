from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Mapping, Sequence, Set

from .contracts import AnalysisModuleStateRecord


@dataclass
class IdempotencyStore:
    processed_run_ids: Set[str] = field(default_factory=set)

    def __init__(self, processed_run_ids: Iterable[str] | None = None) -> None:
        self.processed_run_ids = set(processed_run_ids or ())

    def has_processed(self, run_id: str) -> bool:
        return run_id in self.processed_run_ids

    def mark_processed(self, run_id: str) -> None:
        self.processed_run_ids.add(run_id)


@dataclass
class ModuleStateStore:
    records: List[AnalysisModuleStateRecord] = field(default_factory=list)

    def __init__(self, records: Sequence[AnalysisModuleStateRecord] | None = None) -> None:
        self.records = list(records or [])

    def append(self, record: AnalysisModuleStateRecord) -> None:
        self.records.append(record)

    def all(self) -> Sequence[AnalysisModuleStateRecord]:
        return tuple(self.records)

    def by_symbol(self, symbol: str) -> Sequence[AnalysisModuleStateRecord]:
        return tuple(record for record in self.records if record.symbol == symbol)

    def latest_by_symbol_and_module(self, symbol: str, module_id: str) -> AnalysisModuleStateRecord | None:
        filtered = [record for record in self.records if record.symbol == symbol and record.module_id == module_id]
        if not filtered:
            return None
        return filtered[-1]
