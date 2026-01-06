from __future__ import annotations

from regime_engine.veto.types import VetoResult

VETO_INVALIDATIONS: dict[str, str] = {
    "acceptance_high_veto_chop": "acceptance high veto: chop",
    "acceptance_high_veto_liquidation": "acceptance high veto: liquidation",
    "oi_contracting_atr_expanding_veto_trend_build": (
        "oi contracting + atr expanding veto: trend build"
    ),
    "oi_flat_atr_compressed_force_chop_balanced": "oi flat + atr compressed force: chop balanced",
}


def invalidations_from_vetoes(vetoes: list[VetoResult]) -> list[str]:
    invalidations: list[str] = []
    seen: set[str] = set()
    for veto in vetoes:
        if not veto.vetoed:
            continue
        for reason in veto.reasons:
            invalidation = VETO_INVALIDATIONS.get(reason, reason)
            if invalidation in seen:
                continue
            seen.add(invalidation)
            invalidations.append(invalidation)
    return invalidations
