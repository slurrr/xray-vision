from __future__ import annotations

from regime_engine.contracts.snapshots import ContextSnapshot


def rs_vs_btc(snapshot: ContextSnapshot) -> float:
    return snapshot.rs_vs_btc


def beta_to_btc(snapshot: ContextSnapshot) -> float:
    return snapshot.beta_to_btc


def alt_breadth(snapshot: ContextSnapshot) -> float:
    return snapshot.alt_breadth
