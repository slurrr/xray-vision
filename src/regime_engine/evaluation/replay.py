from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from typing import Any

from regime_engine.evaluation.records import LogRecord
from regime_engine.evaluation.validate import parse_record


def read_records(paths: Sequence[str]) -> list[LogRecord]:
    records: list[LogRecord] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data: dict[str, Any] = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record = parse_record(data)
                if record is None:
                    continue
                records.append(record)
    return records


def group_by_symbol(records: Iterable[LogRecord]) -> dict[str, list[LogRecord]]:
    grouped: dict[str, list[LogRecord]] = defaultdict(list)
    for record in records:
        grouped[record.symbol].append(record)

    prepared: dict[str, list[LogRecord]] = {}
    for symbol, items in grouped.items():
        items.sort(key=lambda item: item.timestamp)
        deduped: list[LogRecord] = []
        last_timestamp: int | None = None
        for item in items:
            if last_timestamp is not None and item.timestamp == last_timestamp:
                continue
            if last_timestamp is not None and item.timestamp < last_timestamp:
                continue
            deduped.append(item)
            last_timestamp = item.timestamp
        prepared[symbol] = deduped
    return prepared


def replay(paths: Sequence[str]) -> dict[str, list[LogRecord]]:
    records = read_records(paths)
    return group_by_symbol(records)
