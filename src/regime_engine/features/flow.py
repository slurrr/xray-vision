from __future__ import annotations

from regime_engine.contracts.snapshots import FlowSnapshot


def cvd_slope(snapshot: FlowSnapshot) -> float:
    return snapshot.cvd_slope


def cvd_efficiency(snapshot: FlowSnapshot) -> float:
    return snapshot.cvd_efficiency


def aggressive_volume_ratio(snapshot: FlowSnapshot) -> float:
    return snapshot.aggressive_volume_ratio
