from __future__ import annotations

from regime_engine.contracts.snapshots import DerivativesSnapshot


def oi_slope_short(snapshot: DerivativesSnapshot) -> float:
    return snapshot.oi_slope_short


def oi_slope_med(snapshot: DerivativesSnapshot) -> float:
    return snapshot.oi_slope_med


def oi_acceleration(snapshot: DerivativesSnapshot) -> float:
    return snapshot.oi_accel


def funding_level(snapshot: DerivativesSnapshot) -> float:
    return snapshot.funding_rate


def funding_slope(snapshot: DerivativesSnapshot) -> float:
    return snapshot.funding_slope


def funding_zscore(snapshot: DerivativesSnapshot) -> float:
    return snapshot.funding_z
