from __future__ import annotations

from regime_engine.matrix.definitions.loader_v1 import load_definition_v1
from regime_engine.matrix.definitions.types_v1 import MatrixDefinitionV1

MATRIX_DEFINITION_V1: MatrixDefinitionV1 | None
MATRIX_DEFINITION_V1_ERROR: str | None = None
try:
    MATRIX_DEFINITION_V1 = load_definition_v1()
except Exception as exc:
    MATRIX_DEFINITION_V1 = None
    MATRIX_DEFINITION_V1_ERROR = str(exc)
