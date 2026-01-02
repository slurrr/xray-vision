from __future__ import annotations

from collections.abc import Callable

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.contracts.snapshots import RegimeInputSnapshot, is_missing
from regime_engine.veto.types import VetoResult

VetoRule = Callable[[RegimeInputSnapshot, list[RegimeScore]], list[VetoResult]]

def acceptance_is_high(acceptance_score: float) -> bool:
    if is_missing(acceptance_score):
        return False
    return False


def oi_is_contracting(oi_slope_short: float, oi_slope_med: float) -> bool:
    if is_missing(oi_slope_short) or is_missing(oi_slope_med):
        return False
    return False


def oi_is_flat(oi_slope_short: float, oi_slope_med: float) -> bool:
    if is_missing(oi_slope_short) or is_missing(oi_slope_med):
        return False
    return False


def atr_is_expanding(atr_zscore: float, range_expansion: float) -> bool:
    if is_missing(atr_zscore) or is_missing(range_expansion):
        return False
    return False


def atr_is_compressed(atr_zscore: float, range_expansion: float) -> bool:
    if is_missing(atr_zscore) or is_missing(range_expansion):
        return False
    return False


def rule_acceptance_high_no_liquidation(
    snapshot: RegimeInputSnapshot,
    scores: list[RegimeScore],
) -> list[VetoResult]:
    _ = scores
    if not acceptance_is_high(snapshot.market.acceptance_score):
        return []
    return [
        VetoResult(
            regime=Regime.LIQUIDATION_UP,
            vetoed=True,
            reasons=["acceptance_high_veto_liquidation"],
        ),
        VetoResult(
            regime=Regime.LIQUIDATION_DOWN,
            vetoed=True,
            reasons=["acceptance_high_veto_liquidation"],
        ),
    ]


def rule_acceptance_high_no_chop(
    snapshot: RegimeInputSnapshot,
    scores: list[RegimeScore],
) -> list[VetoResult]:
    _ = scores
    if not acceptance_is_high(snapshot.market.acceptance_score):
        return []
    return [
        VetoResult(
            regime=Regime.CHOP_BALANCED,
            vetoed=True,
            reasons=["acceptance_high_veto_chop"],
        ),
        VetoResult(
            regime=Regime.CHOP_STOPHUNT,
            vetoed=True,
            reasons=["acceptance_high_veto_chop"],
        ),
    ]


def rule_oi_contracting_atr_expanding_no_trend_build_up(
    snapshot: RegimeInputSnapshot,
    scores: list[RegimeScore],
) -> list[VetoResult]:
    _ = scores
    if not (
        oi_is_contracting(
            snapshot.derivatives.oi_slope_short,
            snapshot.derivatives.oi_slope_med,
        )
        and atr_is_expanding(snapshot.market.atr_z, snapshot.market.range_expansion)
    ):
        return []
    return [
        VetoResult(
            regime=Regime.TREND_BUILD_UP,
            vetoed=True,
            reasons=["oi_contracting_atr_expanding_veto_trend_build"],
        )
    ]


def rule_oi_contracting_atr_expanding_no_trend_build_down(
    snapshot: RegimeInputSnapshot,
    scores: list[RegimeScore],
) -> list[VetoResult]:
    _ = scores
    if not (
        oi_is_contracting(
            snapshot.derivatives.oi_slope_short,
            snapshot.derivatives.oi_slope_med,
        )
        and atr_is_expanding(snapshot.market.atr_z, snapshot.market.range_expansion)
    ):
        return []
    return [
        VetoResult(
            regime=Regime.TREND_BUILD_DOWN,
            vetoed=True,
            reasons=["oi_contracting_atr_expanding_veto_trend_build"],
        )
    ]


def rule_oi_flat_atr_compressed_force_chop_balanced(
    snapshot: RegimeInputSnapshot,
    scores: list[RegimeScore],
) -> list[VetoResult]:
    _ = scores
    if not (
        oi_is_flat(
            snapshot.derivatives.oi_slope_short,
            snapshot.derivatives.oi_slope_med,
        )
        and atr_is_compressed(snapshot.market.atr_z, snapshot.market.range_expansion)
    ):
        return []
    return [
        VetoResult(
            regime=regime,
            vetoed=True,
            reasons=["oi_flat_atr_compressed_force_chop_balanced"],
        )
        for regime in Regime
        if regime is not Regime.CHOP_BALANCED
    ]


_RULES: tuple[VetoRule, ...] = (
    rule_acceptance_high_no_liquidation,
    rule_acceptance_high_no_chop,
    rule_oi_contracting_atr_expanding_no_trend_build_up,
    rule_oi_contracting_atr_expanding_no_trend_build_down,
    rule_oi_flat_atr_compressed_force_chop_balanced,
)


def rule_registry() -> tuple[VetoRule, ...]:
    """Return the deterministic, ordered veto rule registry."""
    return _RULES
