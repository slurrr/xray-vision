from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from regime_engine.evaluation.records import LogRecord


@dataclass(frozen=True)
class FlipFrequency:
    flips: int
    updates: int
    flip_rate_per_update: float
    flip_rate_per_hour: float | None


@dataclass(frozen=True)
class RegimeRun:
    regime: str
    count: int
    start_timestamp: int
    end_timestamp: int
    duration_ms: int


def _get_regime(record: LogRecord, *, key: str) -> str:
    if key == "truth":
        return record.truth_regime
    return record.selected_regime


def regime_persistence(records: list[LogRecord], *, key: str) -> dict[str, list[int]]:
    runs: dict[str, list[int]] = defaultdict(list)
    if not records:
        return {}

    current_regime = _get_regime(records[0], key=key)
    count = 1
    for record in records[1:]:
        regime = _get_regime(record, key=key)
        if regime == current_regime:
            count += 1
            continue
        runs[current_regime].append(count)
        current_regime = regime
        count = 1
    runs[current_regime].append(count)
    return dict(runs)


def regime_runs(records: list[LogRecord], *, key: str) -> list[RegimeRun]:
    if not records:
        return []

    runs: list[RegimeRun] = []
    current_regime = _get_regime(records[0], key=key)
    start_timestamp = records[0].timestamp
    count = 1
    for record in records[1:]:
        regime = _get_regime(record, key=key)
        if regime == current_regime:
            count += 1
            continue
        end_timestamp = record.timestamp
        runs.append(
            RegimeRun(
                regime=current_regime,
                count=count,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                duration_ms=end_timestamp - start_timestamp,
            )
        )
        current_regime = regime
        start_timestamp = record.timestamp
        count = 1

    end_timestamp = records[-1].timestamp
    runs.append(
        RegimeRun(
            regime=current_regime,
            count=count,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            duration_ms=end_timestamp - start_timestamp,
        )
    )
    return runs


def flip_frequency(records: list[LogRecord], *, key: str) -> FlipFrequency:
    if len(records) < 2:
        return FlipFrequency(flips=0, updates=len(records), flip_rate_per_update=0.0, flip_rate_per_hour=None)

    flips = 0
    last_regime = _get_regime(records[0], key=key)
    for record in records[1:]:
        regime = _get_regime(record, key=key)
        if regime != last_regime:
            flips += 1
        last_regime = regime

    updates = len(records)
    duration_ms = records[-1].timestamp - records[0].timestamp
    flip_rate_per_update = flips / (updates - 1) if updates > 1 else 0.0
    flip_rate_per_hour = None
    if duration_ms > 0:
        flip_rate_per_hour = flips / (duration_ms / 3_600_000)

    return FlipFrequency(
        flips=flips,
        updates=updates,
        flip_rate_per_update=flip_rate_per_update,
        flip_rate_per_hour=flip_rate_per_hour,
    )


def time_in_regime(records: list[LogRecord], *, key: str) -> dict[str, int]:
    if len(records) < 2:
        return {}
    totals: dict[str, int] = defaultdict(int)
    for prev, current in zip(records, records[1:]):
        regime = _get_regime(prev, key=key)
        delta = current.timestamp - prev.timestamp
        totals[regime] += delta
    return dict(totals)


def forward_metric_distribution(
    records: list[LogRecord],
    values_by_id: dict[str, float],
    *,
    key: str,
) -> dict[str, list[float]]:
    distribution: dict[str, list[float]] = defaultdict(list)
    for record in records:
        value = values_by_id.get(record.record_id)
        if value is None:
            continue
        regime = _get_regime(record, key=key)
        distribution[regime].append(value)
    return dict(distribution)


def forward_return_distribution(
    records: list[LogRecord],
    forward_returns_by_id: dict[str, float],
    *,
    key: str,
) -> dict[str, list[float]]:
    return forward_metric_distribution(records, forward_returns_by_id, key=key)


def forward_volatility_distribution(
    records: list[LogRecord],
    forward_vol_by_id: dict[str, float],
    *,
    key: str,
) -> dict[str, list[float]]:
    return forward_metric_distribution(records, forward_vol_by_id, key=key)


def regime_expectancy(
    records: list[LogRecord],
    forward_returns_by_id: dict[str, float],
    *,
    key: str,
) -> dict[str, float]:
    distribution = forward_metric_distribution(records, forward_returns_by_id, key=key)
    expectancy: dict[str, float] = {}
    for regime, values in distribution.items():
        if values:
            expectancy[regime] = sum(values) / len(values)
    return expectancy


def summarize(records: list[LogRecord]) -> dict[str, object]:
    return {
        "truth": {
            "persistence": regime_persistence(records, key="truth"),
            "runs": regime_runs(records, key="truth"),
            "flip_frequency": flip_frequency(records, key="truth"),
            "time_in_regime_ms": time_in_regime(records, key="truth"),
        },
        "stabilized": {
            "persistence": regime_persistence(records, key="stabilized"),
            "runs": regime_runs(records, key="stabilized"),
            "flip_frequency": flip_frequency(records, key="stabilized"),
            "time_in_regime_ms": time_in_regime(records, key="stabilized"),
        },
    }
