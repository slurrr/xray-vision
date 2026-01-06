from __future__ import annotations

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.scoring.helpers import score_symmetric

_CHOP_BALANCED_CONTRIBUTORS = [
    "market.atr_zscore",
    "market.range_expansion",
    "flow.cvd_efficiency",
    "derivatives.oi_slope_short",
    "derivatives.funding_level",
]

_CHOP_STOPHUNT_CONTRIBUTORS = [
    "market.sweep_score",
    "market.acceptance_score",
    "market.range_expansion",
    "flow.aggressive_volume_ratio",
    "derivatives.oi_slope_short",
    "derivatives.funding_level",
]

_LIQUIDATION_CONTRIBUTORS = [
    "market.range_expansion",
    "market.atr_zscore",
    "market.sweep_score",
    "flow.cvd_slope",
    "flow.cvd_efficiency",
    "derivatives.oi_acceleration",
    "derivatives.funding_level",
    "derivatives.funding_slope",
    "derivatives.funding_zscore",
]

_SQUEEZE_CONTRIBUTORS = [
    "derivatives.oi_slope_med",
    "derivatives.oi_acceleration",
    "derivatives.funding_zscore",
    "market.range_expansion",
    "flow.cvd_slope",
    "flow.cvd_efficiency",
]

_TREND_BUILD_CONTRIBUTORS = [
    "flow.cvd_slope",
    "flow.cvd_efficiency",
    "market.acceptance_score",
    "market.range_expansion",
    "derivatives.oi_slope_med",
    "derivatives.funding_slope",
    "context.rs_vs_btc",
    "context.beta_to_btc",
    "context.alt_breadth",
]

_TREND_EXHAUSTION_CONTRIBUTORS = [
    "flow.cvd_efficiency",
    "market.sweep_score",
    "market.acceptance_score",
    "market.atr_zscore",
    "derivatives.funding_zscore",
    "derivatives.oi_acceleration",
    "context.rs_vs_btc",
    "context.alt_breadth",
]


def score_chop_balanced(snapshot: RegimeInputSnapshot) -> RegimeScore:
    _ = snapshot
    return RegimeScore(
        regime=Regime.CHOP_BALANCED,
        score=0.0,
        contributors=list(_CHOP_BALANCED_CONTRIBUTORS),
    )


def score_chop_stophunt(snapshot: RegimeInputSnapshot) -> RegimeScore:
    _ = snapshot
    return RegimeScore(
        regime=Regime.CHOP_STOPHUNT,
        score=0.0,
        contributors=list(_CHOP_STOPHUNT_CONTRIBUTORS),
    )


def score_liquidation_up(snapshot: RegimeInputSnapshot) -> RegimeScore:
    return score_symmetric(
        snapshot,
        regime=Regime.LIQUIDATION_UP,
        contributors=_LIQUIDATION_CONTRIBUTORS,
    )


def score_liquidation_down(snapshot: RegimeInputSnapshot) -> RegimeScore:
    return score_symmetric(
        snapshot,
        regime=Regime.LIQUIDATION_DOWN,
        contributors=_LIQUIDATION_CONTRIBUTORS,
    )


def score_squeeze_up(snapshot: RegimeInputSnapshot) -> RegimeScore:
    return score_symmetric(
        snapshot,
        regime=Regime.SQUEEZE_UP,
        contributors=_SQUEEZE_CONTRIBUTORS,
    )


def score_squeeze_down(snapshot: RegimeInputSnapshot) -> RegimeScore:
    return score_symmetric(
        snapshot,
        regime=Regime.SQUEEZE_DOWN,
        contributors=_SQUEEZE_CONTRIBUTORS,
    )


def score_trend_build_up(snapshot: RegimeInputSnapshot) -> RegimeScore:
    return score_symmetric(
        snapshot,
        regime=Regime.TREND_BUILD_UP,
        contributors=_TREND_BUILD_CONTRIBUTORS,
    )


def score_trend_build_down(snapshot: RegimeInputSnapshot) -> RegimeScore:
    return score_symmetric(
        snapshot,
        regime=Regime.TREND_BUILD_DOWN,
        contributors=_TREND_BUILD_CONTRIBUTORS,
    )


def score_trend_exhaustion(snapshot: RegimeInputSnapshot) -> RegimeScore:
    _ = snapshot
    return RegimeScore(
        regime=Regime.TREND_EXHAUSTION,
        score=0.0,
        contributors=list(_TREND_EXHAUSTION_CONTRIBUTORS),
    )
