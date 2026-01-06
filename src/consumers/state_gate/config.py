from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class OperationLimits:
    max_pending: int
    max_block_ms: int | None = None
    max_failures: int | None = None


@dataclass(frozen=True)
class StateGateConfig:
    max_gap_ms: int
    denylisted_invalidations: Sequence[str]
    block_during_transition: bool
    input_limits: OperationLimits
    persistence_limits: OperationLimits
    publish_limits: OperationLimits


def validate_config(config: StateGateConfig) -> None:
    _require_positive(config.max_gap_ms, "max_gap_ms")
    _validate_limits(config.input_limits, "input_limits")
    _validate_limits(config.persistence_limits, "persistence_limits")
    _validate_limits(config.publish_limits, "publish_limits")


def _validate_limits(limits: OperationLimits, field_name: str) -> None:
    _require_positive(limits.max_pending, f"{field_name}.max_pending")
    if limits.max_block_ms is not None:
        _require_positive(limits.max_block_ms, f"{field_name}.max_block_ms")
    if limits.max_failures is not None:
        _require_positive(limits.max_failures, f"{field_name}.max_failures")


def _require_positive(value: int, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0")
