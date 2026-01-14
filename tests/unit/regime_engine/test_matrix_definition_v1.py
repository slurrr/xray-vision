from __future__ import annotations

import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.matrix.definitions import loader_v1
from regime_engine.matrix.definitions.types_v1 import (
    CellDefinition,
    MatrixDefinitionV1,
    MatrixWeights,
    SourceDefaults,
)
from regime_engine.matrix.interpreter_v1 import MatrixInterpreterV1
from regime_engine.state.embedded_neutral_evidence import (
    NeutralEvidenceOpinion as EvidenceOpinion,
)
from regime_engine.state.embedded_neutral_evidence import (
    NeutralEvidenceSnapshot as EvidenceSnapshot,
)


class TestMatrixDefinitionV1(unittest.TestCase):
    def test_parser_rejects_unknown_keys(self) -> None:
        payload = {
            "defaults": {"strength_weight": 0.5, "confidence_weight": 0.5, "extra": 1}
        }
        with self.assertRaises(ValueError):
            loader_v1._parse_definition(payload)

    def test_parser_rejects_out_of_bounds_weight(self) -> None:
        payload = {
            "defaults": {"strength_weight": 1.2, "confidence_weight": 0.5},
            "sources": [],
            "cells": [],
        }
        with self.assertRaises(ValueError):
            loader_v1._parse_definition(payload)

    def test_parser_rejects_invalid_regime(self) -> None:
        payload = {
            "defaults": {"strength_weight": 0.5, "confidence_weight": 0.5},
            "cells": [
                {
                    "source": "source_a",
                    "type": "signal",
                    "direction": "UP",
                    "regime": "UNKNOWN",
                    "strength_weight": 0.5,
                    "confidence_weight": 0.5,
                }
            ],
        }
        with self.assertRaises(ValueError):
            loader_v1._parse_definition(payload)

    def test_interpreter_fallback_order(self) -> None:
        defaults = MatrixWeights(
            strength_weight=1.0,
            confidence_weight=1.0,
            strength_cap=None,
            confidence_cap=None,
        )
        source_defaults = (
            SourceDefaults(
                source="source_a",
                weights=MatrixWeights(
                    strength_weight=0.5,
                    confidence_weight=0.5,
                    strength_cap=None,
                    confidence_cap=None,
                ),
            ),
        )
        cells = (
            CellDefinition(
                source="source_a",
                evidence_type="signal",
                direction="UP",
                regime=Regime.CHOP_BALANCED,
                weights=MatrixWeights(
                    strength_weight=0.2,
                    confidence_weight=0.2,
                    strength_cap=0.1,
                    confidence_cap=0.1,
                ),
            ),
        )
        definition = MatrixDefinitionV1(
            defaults=defaults,
            source_defaults=source_defaults,
            cells=cells,
        )
        interpreter = MatrixInterpreterV1(definition=definition)
        evidence = EvidenceSnapshot(
            symbol="TEST",
            engine_timestamp_ms=123,
            opinions=(
                EvidenceOpinion(
                    type="signal",
                    direction="UP",
                    strength=1.0,
                    confidence=1.0,
                    source="source_a",
                ),
                EvidenceOpinion(
                    type="signal",
                    direction="UP",
                    strength=1.0,
                    confidence=1.0,
                    source="source_a",
                ),
            ),
        )

        result = interpreter.interpret(evidence)

        first = result.influences[0]
        self.assertEqual(first.regime, Regime.CHOP_BALANCED)
        self.assertEqual(first.strength, 0.1)
        self.assertEqual(first.confidence, 0.1)
        self.assertEqual(len(result.influences), 2)


if __name__ == "__main__":
    unittest.main()
