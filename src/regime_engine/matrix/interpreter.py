from __future__ import annotations

from regime_engine.matrix.types import MatrixInterpreter, RegimeInfluenceSet
from regime_engine.state.embedded_neutral_evidence import NeutralEvidenceSnapshot


class ShadowMatrixInterpreter(MatrixInterpreter):
    def interpret(self, evidence: NeutralEvidenceSnapshot) -> RegimeInfluenceSet:
        influences = ()
        return RegimeInfluenceSet(
            symbol=evidence.symbol,
            engine_timestamp_ms=evidence.engine_timestamp_ms,
            influences=influences,
        )
