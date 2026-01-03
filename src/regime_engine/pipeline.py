"""
Internal pipeline implementation (mutable):
snapshot → score → veto → resolve → confidence → explain
"""

from __future__ import annotations

from regime_engine.confidence import synthesize_confidence
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.explainability import build_regime_output
from regime_engine.resolution import resolve_regime
from regime_engine.scoring import score_all


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


def run_pipeline(snapshot: RegimeInputSnapshot) -> RegimeOutput:
    scores = score_all(snapshot)
    resolution = resolve_regime(scores, snapshot, weights={})
    confidence = synthesize_confidence(
        resolution,
        spread_transform=_spread_transform,
        agreement_transform=_agreement_transform,
        veto_penalty_transform=_veto_penalty_transform,
    )
    return build_regime_output(snapshot.symbol, snapshot.timestamp, resolution, confidence)
