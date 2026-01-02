from __future__ import annotations

from regime_engine.contracts.regimes import Regime


REGIME_PERMISSIONS: dict[Regime, list[str]] = {
    Regime.CHOP_BALANCED: [Regime.CHOP_BALANCED.value],
    Regime.CHOP_STOPHUNT: [Regime.CHOP_STOPHUNT.value],
    Regime.LIQUIDATION_UP: [Regime.LIQUIDATION_UP.value],
    Regime.LIQUIDATION_DOWN: [Regime.LIQUIDATION_DOWN.value],
    Regime.SQUEEZE_UP: [Regime.SQUEEZE_UP.value],
    Regime.SQUEEZE_DOWN: [Regime.SQUEEZE_DOWN.value],
    Regime.TREND_BUILD_UP: [Regime.TREND_BUILD_UP.value],
    Regime.TREND_BUILD_DOWN: [Regime.TREND_BUILD_DOWN.value],
    Regime.TREND_EXHAUSTION: [Regime.TREND_EXHAUSTION.value],
}


def permissions_for_regime(regime: Regime) -> list[str]:
    return list(REGIME_PERMISSIONS.get(regime, []))
