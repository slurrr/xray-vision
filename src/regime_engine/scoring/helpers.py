from __future__ import annotations

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot


def score_symmetric(
    snapshot: RegimeInputSnapshot,
    *,
    regime: Regime,
    contributors: list[str],
) -> RegimeScore:
    _ = snapshot
    return RegimeScore(regime=regime, score=0.0, contributors=list(contributors))
