from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from regime_engine.contracts.regimes import Regime

if TYPE_CHECKING:
    from regime_engine.state.evidence import EvidenceOpinion


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

    def log_hysteresis_reset(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        prev_engine_timestamp_ms: int,
        gap_ms: int,
        trigger: str,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.hysteresis.reset",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "prev_engine_timestamp_ms": prev_engine_timestamp_ms,
                "gap_ms": gap_ms,
                "trigger": trigger,
            },
        )

    def log_matrix_shadow(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        evidence_origin: str,
        opinion_count: int,
        opinion_summaries: Sequence[Mapping[str, object]],
        influence_count: int,
        influence_summaries: Sequence[Mapping[str, object]],
        interpreter_status: str,
        error_code: str | None,
        error_type: str | None,
        error_message: str | None,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.matrix.shadow",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "evidence_origin": evidence_origin,
                "opinion_count": opinion_count,
                "opinion_summaries": list(opinion_summaries),
                "influence_count": influence_count,
                "influence_summaries": list(influence_summaries),
                "interpreter_status": interpreter_status,
                "error_code": error_code,
                "error_type": error_type,
                "error_message": error_message,
            },
        )

    def log_matrix_mode(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        requested_mode: str,
        effective_mode: str,
        scope_enabled: bool,
        fail_closed: bool,
        strict_mismatch_fallback: bool,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.matrix.mode",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "requested_mode": requested_mode,
                "effective_mode": effective_mode,
                "scope_enabled": scope_enabled,
                "fail_closed": fail_closed,
                "strict_mismatch_fallback": strict_mismatch_fallback,
            },
        )

    def log_matrix_bridge(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        evidence_origin: str,
        influence_count: int,
        influence_summaries: Sequence[Mapping[str, object]],
        opinion_count: int,
        opinion_summaries: Sequence[Mapping[str, object]],
        status: str,
        error_code: str | None,
        error_type: str | None,
        error_message: str | None,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.matrix.bridge",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "evidence_origin": evidence_origin,
                "influence_count": influence_count,
                "influence_summaries": list(influence_summaries),
                "opinion_count": opinion_count,
                "opinion_summaries": list(opinion_summaries),
                "status": status,
                "error_code": error_code,
                "error_type": error_type,
                "error_message": error_message,
            },
        )

    def log_matrix_diff(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        evidence_origin: str,
        legacy_selected: Mapping[str, object] | None,
        matrix_selected: Mapping[str, object] | None,
        selection_matches: bool | None,
        error_code: str | None,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.matrix.diff",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "evidence_origin": evidence_origin,
                "legacy_selected": legacy_selected,
                "matrix_selected": matrix_selected,
                "selection_matches": selection_matches,
                "error_code": error_code,
            },
        )

    def log_matrix_fallback(
        self,
        *,
        symbol: str,
        engine_timestamp_ms: int,
        evidence_origin: str,
        reason_code: str,
        error_type: str | None,
        error_message: str | None,
    ) -> None:
        self.logger.log(
            logging.INFO,
            "regime_engine.matrix.fallback",
            {
                "symbol": symbol,
                "engine_timestamp_ms": engine_timestamp_ms,
                "evidence_origin": evidence_origin,
                "reason_code": reason_code,
                "error_type": error_type,
                "error_message": error_message,
            },
        )


_OBSERVABILITY = Observability(logger=NullLogger())


def set_observability(observability: Observability) -> None:
    global _OBSERVABILITY
    _OBSERVABILITY = observability


def get_observability() -> Observability:
    return _OBSERVABILITY


def summarize_opinions(
    opinions: Sequence[EvidenceOpinion],
    *,
    max_items: int,
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for opinion in opinions[:max_items]:
        summaries.append(
            {
                "source": opinion.source,
                "regime": opinion.regime.value,
                "strength": opinion.strength,
                "confidence": opinion.confidence,
            }
        )
    return summaries
