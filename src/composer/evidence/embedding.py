from __future__ import annotations

from dataclasses import replace

from composer.contracts.evidence_snapshot import EvidenceSnapshot
from regime_engine.contracts.snapshots import RegimeInputSnapshot

EMBEDDED_NEUTRAL_EVIDENCE_KEY = "composer_evidence_snapshot_neutral_v1"


def embed_neutral_evidence(
    snapshot: RegimeInputSnapshot,
    evidence: EvidenceSnapshot,
) -> RegimeInputSnapshot:
    structure_levels: dict[str, object]
    existing = snapshot.market.structure_levels
    if isinstance(existing, dict):
        structure_levels = dict(existing)
    else:
        structure_levels = {}
    structure_levels[EMBEDDED_NEUTRAL_EVIDENCE_KEY] = _serialize_evidence_snapshot(evidence)
    updated_market = replace(snapshot.market, structure_levels=structure_levels)
    return replace(snapshot, market=updated_market)


def _serialize_evidence_snapshot(snapshot: EvidenceSnapshot) -> dict[str, object]:
    opinions = [
        {
            "type": opinion.type,
            "direction": opinion.direction,
            "strength": opinion.strength,
            "confidence": opinion.confidence,
            "source": opinion.source,
        }
        for opinion in snapshot.opinions
    ]
    return {
        "schema": snapshot.schema,
        "schema_version": snapshot.schema_version,
        "symbol": snapshot.symbol,
        "engine_timestamp_ms": snapshot.engine_timestamp_ms,
        "opinions": opinions,
    }
