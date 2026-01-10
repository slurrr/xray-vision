from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from regime_engine.contracts.regimes import Regime


class StructuredLogger(Protocol):
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None: ...

    def is_enabled_for(self, level: int) -> bool: ...


@dataclass(frozen=True)
class StdlibLogger:
    logger: logging.Logger

    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        self.logger.log(level, message, extra={"fields": dict(fields)})

    def is_enabled_for(self, level: int) -> bool:
        return self.logger.isEnabledFor(level)


@dataclass(frozen=True)
class NullLogger:
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        return None

    def is_enabled_for(self, level: int) -> bool:
        return False


@dataclass(frozen=True)
class Observability:
    logger: StructuredLogger

    def log_engine_entry(self, *, symbol: str, engine_timestamp_ms: int) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.run.start",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
            },
        )

    def log_belief_aggregation(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        anchor_regime: Regime,
        selected_regime: Regime | None,
        belief_by_regime: Mapping[Regime, float],
    ) -> None:
        fields: dict[str, object] = {
            "symbol": symbol,
            "engine_timestamp_ms": engine_timestamp_ms,
            "anchor_regime": anchor_regime.value,
            "selected_regime": selected_regime.value if selected_regime is not None else None,
        }
        if self.logger.is_enabled_for(logging.DEBUG):
            fields["belief_by_regime"] = {
                regime.value: value for regime, value in belief_by_regime.items()
            }
        self.logger.log(logging.INFO, "regime_engine.belief.aggregated", fields)

    def log_hysteresis_transition(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        anchor_prev: Regime | None,
        anchor_next: Regime,
        candidate_regime: Regime | None,
        progress_current: int,
        progress_required: int,
        committed: bool,
        reason_codes: Sequence[str],
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.hysteresis.transition",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "anchor_prev": anchor_prev.value if anchor_prev is not None else None,
                "anchor_next": anchor_next.value,
                "candidate_regime": (
                    candidate_regime.value if candidate_regime is not None else None
                ),
                "progress_current": progress_current,
                "progress_required": progress_required,
                "committed": committed,
                "reason_codes": list(reason_codes),
            },
        )

    def log_hysteresis_decision(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        prior_anchor_regime: Regime | None,
        candidate_regime: Regime | None,
        selected_regime: Regime,
        decision: str,
        window_size: int,
        confirmation_count: int,
        threshold: float,
        belief_margin: float | None,
        reason_code: str,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.hysteresis_decision",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "prior_anchor_regime": (
                    prior_anchor_regime.value if prior_anchor_regime is not None else None
                ),
                "candidate_regime": (
                    candidate_regime.value if candidate_regime is not None else None
                ),
                "selected_regime": selected_regime.value,
                "decision": decision,
                "window_size": window_size,
                "confirmation_count": confirmation_count,
                "threshold": threshold,
                "belief_margin": belief_margin,
                "reason_code": reason_code,
            },
        )


_OBSERVABILITY = Observability(logger=NullLogger())


def set_observability(observability: Observability) -> None:
    global _OBSERVABILITY
    _OBSERVABILITY = observability


def get_observability() -> Observability:
    return _OBSERVABILITY
