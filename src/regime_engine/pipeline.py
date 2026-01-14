"""
Internal pipeline implementation (mutable):
snapshot → score → veto → resolve → confidence → explain
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from regime_engine.confidence import synthesize_confidence
from regime_engine.confidence.types import ConfidenceResult
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.explainability import build_regime_output
from regime_engine.explainability.permissions import permissions_for_regime
from regime_engine.explainability.validate import validate_explainability
from regime_engine.matrix.bridge import influences_to_evidence_snapshot
from regime_engine.matrix.config import (
    MatrixInterpreterKind,
    MatrixMode,
    load_matrix_routing_config,
)
from regime_engine.matrix.definition_v1 import (
    MATRIX_DEFINITION_V1,
    MATRIX_DEFINITION_V1_ERROR,
)
from regime_engine.matrix.interpreter import ShadowMatrixInterpreter
from regime_engine.matrix.interpreter_v1 import MatrixInterpreterV1
from regime_engine.matrix.types import (
    MatrixInterpreter,
    RegimeInfluence,
    RegimeInfluenceSet,
)
from regime_engine.observability import get_observability
from regime_engine.resolution import resolve_regime
from regime_engine.resolution.types import ResolutionResult
from regime_engine.scoring import score_all
from regime_engine.state import (
    build_classical_evidence,
    initialize_state,
    project_regime,
    update_belief,
)
from regime_engine.state.embedded_evidence import (
    EmbeddedEvidenceResult,
    extract_embedded_evidence,
)
from regime_engine.state.embedded_neutral_evidence import (
    EmbeddedNeutralEvidenceResult,
    NeutralEvidenceOpinion,
    NeutralEvidenceSnapshot,
    extract_embedded_neutral_evidence,
)
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot
from regime_engine.state.state import RegimeState
from regime_engine.state.update import select_opinion

_MATRIX_INTERPRETER_SHADOW = ShadowMatrixInterpreter()
_MATRIX_INTERPRETER = _MATRIX_INTERPRETER_SHADOW
_MATRIX_INTERPRETER_V1 = MatrixInterpreterV1(
    definition=MATRIX_DEFINITION_V1,
    error_message=MATRIX_DEFINITION_V1_ERROR,
)
_MATRIX_SHADOW_MAX_ITEMS = 25
_MATRIX_ERROR_MAX_CHARS = 200
_NEUTRAL_EVIDENCE_MAX_ITEMS = 25


@dataclass(frozen=True)
class _MatrixError:
    code: str
    error_type: str
    error_message: str


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _spread_transform(spread: float) -> float:
    return 0.5 * _clamp_unit(spread)


def _agreement_transform(overlap: float) -> float:
    return 0.5 * _clamp_unit(overlap)


def _veto_penalty_transform(_veto_present: bool) -> float:
    return 1.0


def _apply_projection_to_resolution(
    resolution: ResolutionResult,
    projected_regime: RegimeScore | None,
) -> ResolutionResult:
    if resolution.winner is None or projected_regime is None:
        return resolution
    if resolution.winner.regime == projected_regime.regime:
        return resolution
    return ResolutionResult(
        winner=projected_regime,
        runner_up=resolution.runner_up,  # runner up is legacy 
        ranked=resolution.ranked,
        vetoes=resolution.vetoes,
        confidence_inputs=resolution.confidence_inputs,
    )


def _select_matrix_interpreter(kind: MatrixInterpreterKind) -> MatrixInterpreter:
    if kind == MatrixInterpreterKind.V1:
        return _MATRIX_INTERPRETER_V1
    return _MATRIX_INTERPRETER


def run_pipeline_with_state(
    snapshot: RegimeInputSnapshot,
) -> tuple[RegimeOutput, RegimeState]:
    scores = score_all(snapshot)
    resolution = resolve_regime(scores, snapshot, weights={})
    confidence = synthesize_confidence(  # legacy confidence not belief
        resolution,
        spread_transform=_spread_transform,
        agreement_transform=_agreement_transform,
        veto_penalty_transform=_veto_penalty_transform,
    )
    embedded = extract_embedded_evidence(snapshot)
    if embedded is None:
        evidence = build_classical_evidence(
            resolution,
            confidence,
            symbol=snapshot.symbol,
            engine_timestamp_ms=snapshot.timestamp,
        )
    else:
        evidence = embedded.evidence
    evidence_origin = "embedded" if embedded is not None else "classical"
    neutral_result = _extract_neutral_evidence_safely(snapshot)
    _log_neutral_evidence_safely(snapshot, neutral_result)
    matrix_evidence_origin = _matrix_evidence_origin(neutral_result)
    neutral_invalid = neutral_result is not None and neutral_result.invalidations
    config = load_matrix_routing_config()
    scope_enabled = config.is_symbol_enabled(snapshot.symbol)
    effective_mode = config.effective_mode(snapshot.symbol)
    _log_matrix_mode_safely(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
        requested_mode=config.mode.value,
        effective_mode=effective_mode.value,
        scope_enabled=scope_enabled,
        fail_closed=config.fail_closed,
        strict_mismatch_fallback=config.strict_mismatch_fallback,
    )
    interpreter = _select_matrix_interpreter(config.interpreter)
    influence_set, matrix_error = _compute_matrix_influences(
        neutral_result.evidence if neutral_result is not None and not neutral_invalid else None,
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
        evidence_origin=matrix_evidence_origin,
        interpreter=interpreter,
        missing_reason="neutral_evidence_invalid" if neutral_invalid else None,
    )
    matrix_evidence, bridge_error = _bridge_matrix_influences(
        influence_set,
        evidence_origin=evidence_origin,
        interpreter_error=matrix_error,
    )
    legacy_selected = select_opinion(evidence.opinions)
    matrix_selected = None
    if matrix_evidence is not None:
        matrix_selected = select_opinion(matrix_evidence.opinions)
    selection_matches = None
    if legacy_selected is not None and matrix_selected is not None:
        selection_matches = _same_selection(legacy_selected, matrix_selected)
    _log_matrix_diff_safely(
        symbol=evidence.symbol,
        engine_timestamp_ms=evidence.engine_timestamp_ms,
        evidence_origin=evidence_origin,
        legacy_selected=_summarize_selected(legacy_selected),
        matrix_selected=_summarize_selected(matrix_selected),
        selection_matches=selection_matches,
        error_code=(bridge_error.code if bridge_error is not None else None),
    )
    evidence_for_belief = evidence
    if effective_mode == MatrixMode.MATRIX_ENABLED:
        fallback_error = bridge_error or matrix_error
        fallback_reason = None
        if matrix_evidence is None:
            fallback_reason = (
                fallback_error.code if fallback_error is not None else "matrix_missing"
            )
        elif config.strict_mismatch_fallback and selection_matches is False:
            fallback_reason = "matrix_selection_mismatch"
        if fallback_reason is None and matrix_evidence is not None:
            evidence_for_belief = matrix_evidence
        else:
            if fallback_reason is None:
                fallback_reason = "matrix_missing"
            _log_matrix_fallback_safely(
                symbol=evidence.symbol,
                engine_timestamp_ms=evidence.engine_timestamp_ms,
                evidence_origin=evidence_origin,
                reason_code=fallback_reason,
                error=fallback_error,
            )
    prior_state = initialize_state(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
    )
    updated_state = update_belief(prior_state, evidence_for_belief)
    projected = None
    if resolution.winner is not None:
        projected = RegimeScore(
            regime=project_regime(updated_state),
            score=resolution.winner.score,
            contributors=resolution.winner.contributors,
        )
    projected_resolution = _apply_projection_to_resolution(resolution, projected)
    if embedded is None:
        output = build_regime_output(
            snapshot.symbol,
            snapshot.timestamp,
            projected_resolution,
            confidence,
        )
    else:
        output = _build_evidence_output(
            snapshot=snapshot,
            confidence=confidence,
            embedded=embedded,
            projected_regime=project_regime(updated_state),
        )
    return output, updated_state


def _compute_matrix_influences(
    evidence: NeutralEvidenceSnapshot | None,
    *,
    symbol: str,
    engine_timestamp_ms: int,
    evidence_origin: str,
    interpreter: MatrixInterpreter,
    missing_reason: str | None = None,
) -> tuple[RegimeInfluenceSet | None, _MatrixError | None]:
    if evidence is None:
        error_code = missing_reason or "neutral_evidence_missing"
        error = _MatrixError(
            code=error_code,
            error_type="NeutralEvidenceMissing",
            error_message="neutral evidence payload missing",
        )
        _log_matrix_shadow_safely(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            evidence=None,
            influence_set=None,
            interpreter_status="skipped",
            error_code=error.code,
            error_type=error.error_type,
            error_message=error.error_message,
        )
        return None, error
    try:
        influence_set = interpreter.interpret(evidence)
        _log_matrix_shadow_safely(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            evidence=evidence,
            influence_set=influence_set,
            interpreter_status="ok",
            error_code=None,
            error_type=None,
            error_message=None,
        )
        return influence_set, None
    except Exception as exc:
        error = _MatrixError(
            code="matrix_interpreter_exception",
            error_type=type(exc).__name__,
            error_message=_truncate_error_message(str(exc)),
        )
        _log_matrix_shadow_safely(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            evidence=evidence,
            influence_set=None,
            interpreter_status="error",
            error_code=error.code,
            error_type=error.error_type,
            error_message=error.error_message,
        )
        return None, error


def _bridge_matrix_influences(
    influence_set: RegimeInfluenceSet | None,
    *,
    evidence_origin: str,
    interpreter_error: _MatrixError | None,
) -> tuple[EvidenceSnapshot | None, _MatrixError | None]:
    if influence_set is None:
        _log_matrix_bridge_safely(
            evidence_origin=evidence_origin,
            influence_set=None,
            matrix_evidence=None,
            status="error",
            error=interpreter_error,
        )
        return None, interpreter_error
    try:
        matrix_evidence = influences_to_evidence_snapshot(influence_set)
        _log_matrix_bridge_safely(
            evidence_origin=evidence_origin,
            influence_set=influence_set,
            matrix_evidence=matrix_evidence,
            status="ok",
            error=None,
        )
        return matrix_evidence, None
    except Exception as exc:
        error = _MatrixError(
            code="matrix_bridge_exception",
            error_type=type(exc).__name__,
            error_message=_truncate_error_message(str(exc)),
        )
        _log_matrix_bridge_safely(
            evidence_origin=evidence_origin,
            influence_set=influence_set,
            matrix_evidence=None,
            status="error",
            error=error,
        )
        return None, error


def _log_matrix_shadow_safely(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    evidence_origin: str,
    evidence: NeutralEvidenceSnapshot | None,
    influence_set: RegimeInfluenceSet | None,
    interpreter_status: str,
    error_code: str | None,
    error_type: str | None,
    error_message: str | None,
) -> None:
    try:
        opinions: Sequence[NeutralEvidenceOpinion] = ()
        if evidence is not None:
            opinions = evidence.opinions
        influences: Sequence[RegimeInfluence] = ()
        if influence_set is not None:
            influences = influence_set.influences
        get_observability().log_matrix_shadow(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            opinion_count=len(opinions),
            opinion_summaries=_summarize_neutral_opinions(opinions),
            influence_count=len(influences),
            influence_summaries=_summarize_influences(influences),
            interpreter_status=interpreter_status,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message,
        )
    except Exception:
        return None


def _extract_neutral_evidence_safely(
    snapshot: RegimeInputSnapshot,
) -> EmbeddedNeutralEvidenceResult | None:
    try:
        return extract_embedded_neutral_evidence(snapshot)
    except Exception:
        return None


def _log_neutral_evidence_safely(
    snapshot: RegimeInputSnapshot,
    result: EmbeddedNeutralEvidenceResult | None,
) -> None:
    try:
        if result is None:
            get_observability().log_neutral_evidence(
                symbol=snapshot.symbol,
                engine_timestamp_ms=snapshot.timestamp,
                payload_present=False,
                opinion_count=0,
                opinion_summaries=(),
                invalidations=(),
            )
            return
        summaries = _summarize_neutral_opinions(result.evidence.opinions)
        get_observability().log_neutral_evidence(
            symbol=snapshot.symbol,
            engine_timestamp_ms=snapshot.timestamp,
            payload_present=True,
            opinion_count=len(result.evidence.opinions),
            opinion_summaries=summaries,
            invalidations=result.invalidations,
        )
    except Exception:
        return None


def _matrix_evidence_origin(result: EmbeddedNeutralEvidenceResult | None) -> str:
    if result is None:
        return "missing"
    if result.invalidations:
        return "neutral_invalid"
    return "neutral"


def _log_matrix_mode_safely(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    requested_mode: str,
    effective_mode: str,
    scope_enabled: bool,
    fail_closed: bool,
    strict_mismatch_fallback: bool,
) -> None:
    try:
        get_observability().log_matrix_mode(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            requested_mode=requested_mode,
            effective_mode=effective_mode,
            scope_enabled=scope_enabled,
            fail_closed=fail_closed,
            strict_mismatch_fallback=strict_mismatch_fallback,
        )
    except Exception:
        return None


def _log_matrix_bridge_safely(
    *,
    evidence_origin: str,
    influence_set: RegimeInfluenceSet | None,
    matrix_evidence: EvidenceSnapshot | None,
    status: str,
    error: _MatrixError | None,
) -> None:
    try:
        influence_summaries: Sequence[dict[str, object]] = ()
        influence_count = 0
        if influence_set is not None:
            influence_summaries = _summarize_influences(influence_set.influences)
            influence_count = len(influence_set.influences)
        opinion_summaries: Sequence[dict[str, object]] = ()
        opinion_count = 0
        symbol = None
        engine_timestamp_ms = None
        if matrix_evidence is not None:
            opinion_summaries = _summarize_opinions(matrix_evidence.opinions)
            opinion_count = len(matrix_evidence.opinions)
            symbol = matrix_evidence.symbol
            engine_timestamp_ms = matrix_evidence.engine_timestamp_ms
        elif influence_set is not None:
            symbol = influence_set.symbol
            engine_timestamp_ms = influence_set.engine_timestamp_ms
        if symbol is None or engine_timestamp_ms is None:
            return None
        get_observability().log_matrix_bridge(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            influence_count=influence_count,
            influence_summaries=influence_summaries,
            opinion_count=opinion_count,
            opinion_summaries=opinion_summaries,
            status=status,
            error_code=(error.code if error is not None else None),
            error_type=(error.error_type if error is not None else None),
            error_message=(error.error_message if error is not None else None),
        )
    except Exception:
        return None


def _log_matrix_diff_safely(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    evidence_origin: str,
    legacy_selected: Mapping[str, object] | None,
    matrix_selected: Mapping[str, object] | None,
    selection_matches: bool | None,
    error_code: str | None,
) -> None:
    try:
        get_observability().log_matrix_diff(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            legacy_selected=legacy_selected,
            matrix_selected=matrix_selected,
            selection_matches=selection_matches,
            error_code=error_code,
        )
    except Exception:
        return None


def _log_matrix_fallback_safely(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    evidence_origin: str,
    reason_code: str,
    error: _MatrixError | None,
) -> None:
    try:
        get_observability().log_matrix_fallback(
            symbol=symbol,
            engine_timestamp_ms=engine_timestamp_ms,
            evidence_origin=evidence_origin,
            reason_code=reason_code,
            error_type=(error.error_type if error is not None else None),
            error_message=(error.error_message if error is not None else None),
        )
    except Exception:
        return None


def _summarize_selected(
    opinion: EvidenceOpinion | None,
) -> dict[str, object] | None:
    if opinion is None:
        return None
    return {
        "source": opinion.source,
        "regime": opinion.regime.value,
        "strength": opinion.strength,
        "confidence": opinion.confidence,
    }


def _same_selection(left: EvidenceOpinion, right: EvidenceOpinion) -> bool:
    return (
        left.regime == right.regime
        and left.strength == right.strength
        and left.confidence == right.confidence
        and left.source == right.source
    )


def _truncate_error_message(message: str) -> str:
    if len(message) <= _MATRIX_ERROR_MAX_CHARS:
        return message
    return message[:_MATRIX_ERROR_MAX_CHARS]


def _summarize_opinions(opinions: Sequence[EvidenceOpinion]) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for opinion in opinions[:_MATRIX_SHADOW_MAX_ITEMS]:
        summaries.append(
            {
                "source": opinion.source,
                "regime": opinion.regime.value,
                "strength": opinion.strength,
                "confidence": opinion.confidence,
            }
        )
    return summaries


def _summarize_neutral_opinions(
    opinions: Sequence[NeutralEvidenceOpinion],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for opinion in opinions[:_NEUTRAL_EVIDENCE_MAX_ITEMS]:
        summaries.append(
            {
                "type": opinion.type,
                "direction": opinion.direction,
                "strength": opinion.strength,
                "confidence": opinion.confidence,
                "source": opinion.source,
            }
        )
    return summaries


def _summarize_influences(
    influences: Sequence[RegimeInfluence],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for influence in influences[:_MATRIX_SHADOW_MAX_ITEMS]:
        summaries.append(
            {
                "source": influence.source,
                "regime": influence.regime.value,
                "strength": influence.strength,
                "confidence": influence.confidence,
            }
        )
    return summaries


def run_pipeline(snapshot: RegimeInputSnapshot) -> RegimeOutput:
    output, _state = run_pipeline_with_state(snapshot)
    return output


def _build_evidence_output(
    *,
    snapshot: RegimeInputSnapshot,
    confidence: ConfidenceResult,
    embedded: EmbeddedEvidenceResult,
    projected_regime: Regime,
) -> RegimeOutput:
    drivers = embedded.drivers
    invalidations = embedded.invalidations
    permissions = permissions_for_regime(projected_regime)
    projected_score = RegimeScore(
        regime=projected_regime,
        score=0.0,
        contributors=[],
    )
    validate_explainability(projected_score, drivers, invalidations, permissions)

    confidence_value = confidence.confidence if confidence.confidence is not None else 0.0
    return RegimeOutput(
        symbol=snapshot.symbol,
        timestamp=snapshot.timestamp,
        regime=projected_regime,
        confidence=confidence_value,
        drivers=drivers,
        invalidations=invalidations,
        permissions=permissions,
    )
