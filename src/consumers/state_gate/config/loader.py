from __future__ import annotations

import importlib
from collections.abc import Mapping
from importlib import resources

from consumers.state_gate.config.schema import (
    OperationLimits,
    StateGateConfig,
    validate_config,
)

_ROOT_KEYS = {
    "max_gap_ms",
    "denylisted_invalidations",
    "block_during_transition",
    "input_limits",
    "persistence_limits",
    "publish_limits",
}
_LIMIT_KEYS = {"max_pending", "max_block_ms", "max_failures"}


def load_default_config() -> StateGateConfig:
    payload = _load_default_payload()
    config = _parse_config(payload)
    validate_config(config)
    return config


def _load_default_payload() -> Mapping[str, object]:
    text = (
        resources.files("consumers.state_gate.config")
        .joinpath("default.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("state_gate default config must be a mapping")
    return data


def _parse_config(payload: Mapping[str, object]) -> StateGateConfig:
    _reject_unknown(payload, _ROOT_KEYS, "state_gate config")
    max_gap_ms = payload.get("max_gap_ms")
    denylisted_invalidations = payload.get("denylisted_invalidations")
    block_during_transition = payload.get("block_during_transition")
    input_limits = _parse_limits(payload.get("input_limits"), "input_limits")
    persistence_limits = _parse_limits(payload.get("persistence_limits"), "persistence_limits")
    publish_limits = _parse_limits(payload.get("publish_limits"), "publish_limits")
    if not isinstance(max_gap_ms, int):
        raise ValueError("max_gap_ms must be an int")
    if not isinstance(denylisted_invalidations, list):
        raise ValueError("denylisted_invalidations must be a list")
    if not isinstance(block_during_transition, bool):
        raise ValueError("block_during_transition must be a boolean")
    return StateGateConfig(
        max_gap_ms=max_gap_ms,
        denylisted_invalidations=[str(item) for item in denylisted_invalidations],
        block_during_transition=block_during_transition,
        input_limits=input_limits,
        persistence_limits=persistence_limits,
        publish_limits=publish_limits,
    )


def _parse_limits(data: object, label: str) -> OperationLimits:
    if not isinstance(data, Mapping):
        raise ValueError(f"{label} must be a mapping")
    _reject_unknown(data, _LIMIT_KEYS, label)
    max_pending = data.get("max_pending")
    max_block_ms = data.get("max_block_ms")
    max_failures = data.get("max_failures")
    if not isinstance(max_pending, int):
        raise ValueError(f"{label}.max_pending must be an int")
    if max_block_ms is not None and not isinstance(max_block_ms, int):
        raise ValueError(f"{label}.max_block_ms must be an int")
    if max_failures is not None and not isinstance(max_failures, int):
        raise ValueError(f"{label}.max_failures must be an int")
    return OperationLimits(
        max_pending=max_pending,
        max_block_ms=max_block_ms,
        max_failures=max_failures,
    )


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
