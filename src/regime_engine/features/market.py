from __future__ import annotations

from regime_engine.contracts.snapshots import MarketSnapshot


def atr(snapshot: MarketSnapshot) -> float:
    return snapshot.atr


def atr_zscore(snapshot: MarketSnapshot) -> float:
    return snapshot.atr_z


def range_expansion(snapshot: MarketSnapshot) -> float:
    return snapshot.range_expansion


def acceptance_score(snapshot: MarketSnapshot) -> float:
    return snapshot.acceptance_score


def sweep_score(snapshot: MarketSnapshot) -> float:
    return snapshot.sweep_score
