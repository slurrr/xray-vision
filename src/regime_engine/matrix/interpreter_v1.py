from __future__ import annotations

from regime_engine.matrix.definitions.types_v1 import MatrixDefinitionV1
from regime_engine.matrix.types import MatrixInterpreter, RegimeInfluence, RegimeInfluenceSet
from regime_engine.state.embedded_neutral_evidence import (
    NeutralEvidenceOpinion,
    NeutralEvidenceSnapshot,
)


class MatrixInterpreterV1(MatrixInterpreter):
    def __init__(
        self,
        *,
        definition: MatrixDefinitionV1 | None,
        error_message: str | None = None,
    ) -> None:
        self._definition = definition
        self._error_message = error_message

    def interpret(self, evidence: NeutralEvidenceSnapshot) -> RegimeInfluenceSet:
        if self._definition is None:
            raise RuntimeError(self._error_message or "matrix definition unavailable")
        influences: list[RegimeInfluence] = []
        for opinion in evidence.opinions:
            influences.extend(self._to_influences(opinion))
        ordered = sorted(
            influences,
            key=lambda influence: (
                influence.regime.value,
                influence.source,
                -influence.confidence,
                -influence.strength,
            ),
        )
        return RegimeInfluenceSet(
            symbol=evidence.symbol,
            engine_timestamp_ms=evidence.engine_timestamp_ms,
            influences=tuple(ordered),
        )

    def _to_influences(
        self, opinion: NeutralEvidenceOpinion
    ) -> list[RegimeInfluence]:
        definition = self._definition
        assert definition is not None
        cells = definition.cells_for(
            source=opinion.source,
            evidence_type=opinion.type,
            direction=opinion.direction,
        )
        if not cells:
            return []
        influences: list[RegimeInfluence] = []
        for cell in cells:
            weights = cell.weights
            strength = _apply_weight(
                opinion.strength, weights.strength_weight, weights.strength_cap
            )
            confidence = _apply_weight(
                opinion.confidence, weights.confidence_weight, weights.confidence_cap
            )
            influences.append(
                RegimeInfluence(
                    regime=cell.regime,
                    strength=strength,
                    confidence=confidence,
                    source=f"matrix_v1:{opinion.source}:{opinion.type}:{opinion.direction}",
                )
            )
        return influences


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _apply_weight(value: float, weight: float, cap: float | None) -> float:
    scaled = _clamp_unit(value * weight)
    if cap is None:
        return scaled
    return min(scaled, cap)
