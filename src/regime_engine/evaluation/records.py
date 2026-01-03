from __future__ import annotations

from dataclasses import dataclass


def record_id_for(symbol: str, timestamp: int) -> str:
    return f"{symbol}:{timestamp}"


@dataclass(frozen=True)
class TransitionRecord:
    stable_regime: str | None
    candidate_regime: str | None
    candidate_count: int
    transition_active: bool
    flipped: bool
    reset_due_to_gap: bool


@dataclass(frozen=True)
class LogRecord:
    schema_version: int
    record_id: str
    symbol: str
    timestamp: int
    truth_regime: str
    truth_confidence: float
    drivers: list[str]
    invalidations: list[str]
    permissions: list[str]
    selected_regime: str
    effective_confidence: float
    transition: TransitionRecord

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "truth_regime": self.truth_regime,
            "truth_confidence": self.truth_confidence,
            "drivers": list(self.drivers),
            "invalidations": list(self.invalidations),
            "permissions": list(self.permissions),
            "selected_regime": self.selected_regime,
            "effective_confidence": self.effective_confidence,
            "transition": {
                "stable_regime": self.transition.stable_regime,
                "candidate_regime": self.transition.candidate_regime,
                "candidate_count": self.transition.candidate_count,
                "transition_active": self.transition.transition_active,
                "flipped": self.transition.flipped,
                "reset_due_to_gap": self.transition.reset_due_to_gap,
            },
        }
