from __future__ import annotations

from dataclasses import fields, is_dataclass, dataclass
from typing import Any, Optional


class _Missing:
    __slots__ = ()

    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


def is_missing(value: object) -> bool:
    return value is MISSING


def missing_paths(value: object, *, root: str = "") -> frozenset[str]:
    paths: set[str] = set()

    def add_path(path: str) -> None:
        if path:
            paths.add(path)

    def visit(obj: object, path: str) -> None:
        if is_missing(obj):
            add_path(path)
            return

        if is_dataclass(obj):
            for f in fields(obj):
                child = getattr(obj, f.name)
                child_path = f"{path}.{f.name}" if path else f.name
                visit(child, child_path)
            return

        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                child_path = f"{path}.{key}" if path else key
                visit(v, child_path)
            return

        if isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                child_path = f"{path}[{i}]" if path else f"[{i}]"
                visit(v, child_path)
            return
        
        # terminal scalar → nothing to recurse into
        return

    visit(value, root)
    return frozenset(paths)


@dataclass(frozen=True)
class MarketSnapshot:
    price: float
    vwap: float
    atr: float
    atr_z: float
    range_expansion: float
    structure_levels: dict
    acceptance_score: float
    sweep_score: float


@dataclass(frozen=True)
class DerivativesSnapshot:
    open_interest: float
    oi_slope_short: float
    oi_slope_med: float
    oi_accel: float
    funding_rate: float
    funding_slope: float
    funding_z: float
    liquidation_intensity: Optional[float]


@dataclass(frozen=True)
class FlowSnapshot:
    cvd: float
    cvd_slope: float
    cvd_efficiency: float
    aggressive_volume_ratio: float


@dataclass(frozen=True)
class ContextSnapshot:
    rs_vs_btc: float
    beta_to_btc: float
    alt_breadth: float
    btc_regime: Optional[str]
    eth_regime: Optional[str]


@dataclass(frozen=True)
class RegimeInputSnapshot:
    symbol: str
    timestamp: int  # ms, aligned to 3m close

    market: MarketSnapshot
    derivatives: DerivativesSnapshot
    flow: FlowSnapshot
    context: ContextSnapshot

