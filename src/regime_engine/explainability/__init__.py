from __future__ import annotations

from typing import cast

from regime_engine.confidence.types import ConfidenceResult
from regime_engine.contracts.outputs import RegimeOutput
from regime_engine.contracts.regimes import RegimeScore
from regime_engine.explainability.drivers import drivers_from_contributors
from regime_engine.explainability.invalidations import invalidations_from_vetoes
from regime_engine.explainability.permissions import permissions_for_regime
from regime_engine.explainability.validate import validate_explainability
from regime_engine.resolution.types import ResolutionResult


def build_regime_output(
    symbol: str,
    timestamp: int,
    resolution: ResolutionResult,
    confidence: ConfidenceResult,
) -> RegimeOutput:
    winner = resolution.winner
    drivers = drivers_from_contributors(winner.contributors) if winner else []
    invalidations = invalidations_from_vetoes(resolution.vetoes)
    permissions = permissions_for_regime(winner.regime) if winner else []

    validate_explainability(winner, drivers, invalidations, permissions)

    winner_value = cast(RegimeScore, winner)
    confidence_value = cast(float, confidence.confidence)
    return RegimeOutput(
        symbol=symbol,
        timestamp=timestamp,
        regime=winner_value.regime,
        confidence=confidence_value,
        drivers=drivers,
        invalidations=invalidations,
        permissions=permissions,
    )
