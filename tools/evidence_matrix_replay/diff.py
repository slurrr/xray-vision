from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_REGIME_OUTPUTS_FILENAME = "regime_outputs.jsonl"
_HYSTERESIS_STATES_FILENAME = "hysteresis_states.jsonl"
_PERSISTENCE_COUNTS_FILENAME = "persistence_counts.json"

_HYSTERESIS_IGNORE_FIELDS = {"last_commit_timestamp_ms"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diff replay outputs.")
    parser.add_argument("--baseline-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    return parser.parse_args()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_hysteresis(state: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(state)
    for field in _HYSTERESIS_IGNORE_FIELDS:
        normalized.pop(field, None)
    return normalized


def _normalize_sequence(
    items: Sequence[Mapping[str, Any]],
    *,
    normalize_item,
) -> list[dict[str, Any]]:
    return [normalize_item(item) for item in items]


def _assert_equal_sequence(
    label: str,
    baseline: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
    *,
    normalize_item,
) -> None:
    baseline_norm = _normalize_sequence(baseline, normalize_item=normalize_item)
    candidate_norm = _normalize_sequence(candidate, normalize_item=normalize_item)
    if baseline_norm != candidate_norm:
        raise AssertionError(f"{label} mismatch")


def _assert_equal_counts(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> None:
    if baseline != candidate:
        raise AssertionError("persistence_counts mismatch")


def _assert_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")


def _main() -> None:
    args = _parse_args()
    baseline_dir: Path = args.baseline_dir
    candidate_dir: Path = args.candidate_dir

    baseline_regime = baseline_dir / _REGIME_OUTPUTS_FILENAME
    candidate_regime = candidate_dir / _REGIME_OUTPUTS_FILENAME
    baseline_hysteresis = baseline_dir / _HYSTERESIS_STATES_FILENAME
    candidate_hysteresis = candidate_dir / _HYSTERESIS_STATES_FILENAME
    baseline_counts = baseline_dir / _PERSISTENCE_COUNTS_FILENAME
    candidate_counts = candidate_dir / _PERSISTENCE_COUNTS_FILENAME

    _assert_exists(baseline_regime, "regime_outputs")
    _assert_exists(candidate_regime, "regime_outputs")
    _assert_exists(baseline_hysteresis, "hysteresis_states")
    _assert_exists(candidate_hysteresis, "hysteresis_states")
    _assert_exists(baseline_counts, "persistence_counts")
    _assert_exists(candidate_counts, "persistence_counts")

    baseline_regime_items = _load_jsonl(baseline_regime)
    candidate_regime_items = _load_jsonl(candidate_regime)
    baseline_hysteresis_items = _load_jsonl(baseline_hysteresis)
    candidate_hysteresis_items = _load_jsonl(candidate_hysteresis)
    baseline_counts_item = _load_json(baseline_counts)
    candidate_counts_item = _load_json(candidate_counts)

    _assert_equal_sequence(
        "regime_outputs",
        baseline_regime_items,
        candidate_regime_items,
        normalize_item=lambda item: dict(item),
    )
    _assert_equal_sequence(
        "hysteresis_states",
        baseline_hysteresis_items,
        candidate_hysteresis_items,
        normalize_item=_normalize_hysteresis,
    )
    _assert_equal_counts(baseline_counts_item, candidate_counts_item)
    print(json.dumps({"status": "ok"}, separators=(",", ":")))


if __name__ == "__main__":
    _main()
