"""
Internal pipeline implementation (mutable):
snapshot → score → veto → resolve → confidence → explain
"""

from __future__ import annotations

from regime_engine.confidence import synthesize_confidence
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.explainability import build_regime_output
from regime_engine.resolution import resolve_regime
from regime_engine.resolution.types import ResolutionResult
from regime_engine.scoring import score_all
from regime_engine.state import (
    build_classical_evidence,
    initialize_state,
    project_regime,
    update_belief,
)


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


def run_pipeline(snapshot: RegimeInputSnapshot) -> RegimeOutput:
    scores = score_all(snapshot)
    resolution = resolve_regime(scores, snapshot, weights={})
    confidence = synthesize_confidence(  # legacy confidence not belief
        resolution,
        spread_transform=_spread_transform,
        agreement_transform=_agreement_transform,
        veto_penalty_transform=_veto_penalty_transform,
    )
    evidence = build_classical_evidence(
        resolution,
        confidence,
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
    )
    # NOTE: RegimeState is currently re-initialized per run.
    # Persistence and hysteresis will be introduced in Phase 4.
    prior_state = initialize_state(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
    )
    updated_state = update_belief(prior_state, evidence)
    projected = None
    if resolution.winner is not None:
        projected = RegimeScore(
            regime=project_regime(updated_state),
            score=resolution.winner.score,
            contributors=resolution.winner.contributors,
        )
    projected_resolution = _apply_projection_to_resolution(resolution, projected)
    return build_regime_output(
        snapshot.symbol,
        snapshot.timestamp,
        projected_resolution,
        confidence,
    )
