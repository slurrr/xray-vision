from __future__ import annotations

from dataclasses import dataclass, field

from regime_engine.contracts.regimes import Regime


@dataclass(frozen=True)
class MatrixWeights:
    strength_weight: float
    confidence_weight: float
    strength_cap: float | None
    confidence_cap: float | None


@dataclass(frozen=True)
class SourceDefaults:
    source: str
    weights: MatrixWeights


@dataclass(frozen=True)
class CellDefinition:
    source: str
    evidence_type: str
    direction: str
    regime: Regime
    weights: MatrixWeights


@dataclass(frozen=True)
class MatrixDefinitionV1:
    defaults: MatrixWeights
    source_defaults: tuple[SourceDefaults, ...]
    cells: tuple[CellDefinition, ...]
    _source_map: dict[str, MatrixWeights] = field(init=False, repr=False)
    _cell_map: dict[tuple[str, str, str], tuple[CellDefinition, ...]] = field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        source_map = {entry.source: entry.weights for entry in self.source_defaults}
        cell_map: dict[tuple[str, str, str], list[CellDefinition]] = {}
        for entry in self.cells:
            key = (entry.source, entry.evidence_type, entry.direction)
            cell_map.setdefault(key, []).append(entry)
        ordered_cells = {
            key: tuple(sorted(items, key=lambda item: item.regime.value))
            for key, items in cell_map.items()
        }
        object.__setattr__(self, "_source_map", source_map)
        object.__setattr__(self, "_cell_map", ordered_cells)

    def cells_for(
        self, *, source: str, evidence_type: str, direction: str
    ) -> tuple[CellDefinition, ...]:
        return self._cell_map.get((source, evidence_type, direction), ())

    def default_weights_for(self, *, source: str) -> MatrixWeights:
        source_weights = self._source_map.get(source)
        if source_weights is not None:
            return source_weights
        return self.defaults
