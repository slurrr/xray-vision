from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum


class MatrixMode(str, Enum):
    LEGACY_ONLY = "legacy_only"
    DUAL_RUN = "dual_run"
    MATRIX_ENABLED = "matrix_enabled"


class MatrixInterpreterKind(str, Enum):
    SHADOW = "shadow"
    V1 = "v1"


@dataclass(frozen=True)
class MatrixRoutingConfig:
    mode: MatrixMode
    interpreter: MatrixInterpreterKind
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


def validate_config(config: MatrixRoutingConfig) -> None:
    if not isinstance(config.mode, MatrixMode):
        raise ValueError("mode must be a MatrixMode")
    if not isinstance(config.interpreter, MatrixInterpreterKind):
        raise ValueError("interpreter must be a MatrixInterpreterKind")
    if config.rollout_percent < 0 or config.rollout_percent > 100:
        raise ValueError("rollout_percent must be between 0 and 100")
    for symbol in config.symbol_allowlist:
        if not symbol:
            raise ValueError("symbol_allowlist entries must be non-empty")


def _stable_percent(symbol: str) -> int:
    digest = hashlib.sha256(symbol.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100
