from __future__ import annotations

from regime_engine.contracts.regimes import RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.scoring.stubs import (
    score_chop_balanced,
    score_chop_stophunt,
    score_liquidation_down,
    score_liquidation_up,
    score_squeeze_down,
    score_squeeze_up,
    score_trend_build_down,
    score_trend_build_up,
    score_trend_exhaustion,
)


def score_all(snapshot: RegimeInputSnapshot) -> list[RegimeScore]:
    return [
        score_chop_balanced(snapshot),
        score_chop_stophunt(snapshot),
        score_liquidation_up(snapshot),
        score_liquidation_down(snapshot),
        score_squeeze_up(snapshot),
        score_squeeze_down(snapshot),
        score_trend_build_up(snapshot),
        score_trend_build_down(snapshot),
        score_trend_exhaustion(snapshot),
    ]
