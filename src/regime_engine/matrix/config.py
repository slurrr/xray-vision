from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from enum import Enum


class MatrixMode(str, Enum):
    LEGACY_ONLY = "legacy_only"
    DUAL_RUN = "dual_run"
    MATRIX_ENABLED = "matrix_enabled"


@dataclass(frozen=True)
class MatrixRoutingConfig:
    mode: MatrixMode
    symbol_allowlist: frozenset[str]
    rollout_percent: int
    fail_closed: bool
    strict_mismatch_fallback: bool

    def is_symbol_enabled(self, symbol: str) -> bool:
        if self.symbol_allowlist:
            return symbol in self.symbol_allowlist
        if self.rollout_percent <= 0:
            return False
        if self.rollout_percent >= 100:
            return True
        return _stable_percent(symbol) < self.rollout_percent

    def effective_mode(self, symbol: str) -> MatrixMode:
        if not self.is_symbol_enabled(symbol):
            return MatrixMode.LEGACY_ONLY
        return self.mode


def load_matrix_routing_config() -> MatrixRoutingConfig:
    mode = _parse_mode(os.getenv("REGIME_ENGINE_MATRIX_MODE", "legacy_only"))
    symbol_allowlist = _parse_allowlist(
        os.getenv("REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST", "")
    )
    rollout_percent = _parse_percent(
        os.getenv("REGIME_ENGINE_MATRIX_PERCENT", "0"),
        default=0,
    )
    fail_closed = _parse_bool(os.getenv("REGIME_ENGINE_MATRIX_FAIL_CLOSED", "true"))
    strict_mismatch_fallback = _parse_bool(
        os.getenv("REGIME_ENGINE_MATRIX_STRICT_MISMATCH_FALLBACK", "false")
    )
    return MatrixRoutingConfig(
        mode=mode,
        symbol_allowlist=symbol_allowlist,
        rollout_percent=rollout_percent,
        fail_closed=fail_closed,
        strict_mismatch_fallback=strict_mismatch_fallback,
    )


def _parse_mode(value: str) -> MatrixMode:
    normalized = value.strip().lower()
    for mode in MatrixMode:
        if mode.value == normalized:
            return mode
    return MatrixMode.LEGACY_ONLY


def _parse_allowlist(value: str) -> frozenset[str]:
    if not value.strip():
        return frozenset()
    symbols = {item.strip() for item in value.split(",") if item.strip()}
    return frozenset(symbols)


def _parse_percent(value: str, *, default: int) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(0, min(100, parsed))


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return False


def _stable_percent(symbol: str) -> int:
    digest = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100
