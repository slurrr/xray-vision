from __future__ import annotations

from dataclasses import replace

from composer.observability import get_observability
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.state.evidence import EvidenceSnapshot

EMBEDDED_EVIDENCE_KEY = "composer_evidence_snapshot_v1"


def _serialize_evidence_snapshot(snapshot: EvidenceSnapshot) -> dict[str, object]:
    opinions = [
        {
            "regime": opinion.regime.value,
            "strength": opinion.strength,
            "confidence": opinion.confidence,
            "source": opinion.source,
        }
        for opinion in snapshot.opinions
    ]
    return {
        "symbol": snapshot.symbol,
        "engine_timestamp_ms": snapshot.engine_timestamp_ms,
        "opinions": opinions,
    }


def embed_engine_evidence(
    snapshot: RegimeInputSnapshot,
    evidence: EvidenceSnapshot,
) -> RegimeInputSnapshot:
    opinion_count = len(evidence.opinions)
    if not evidence.opinions:
        existing = snapshot.market.structure_levels
        if not isinstance(existing, dict) or EMBEDDED_EVIDENCE_KEY not in existing:
            get_observability().log_embed_decision(
                symbol=evidence.symbol,
                engine_timestamp_ms=evidence.engine_timestamp_ms,
                opinion_count=opinion_count,
                written=False,
            )
            return snapshot
        structure_levels = dict(existing)
        structure_levels.pop(EMBEDDED_EVIDENCE_KEY, None)
        updated_market = replace(snapshot.market, structure_levels=structure_levels)
        get_observability().log_embed_decision(
            symbol=evidence.symbol,
            engine_timestamp_ms=evidence.engine_timestamp_ms,
            opinion_count=opinion_count,
            written=False,
        )
        return replace(snapshot, market=updated_market)

    structure_levels: dict[str, object]
    existing = snapshot.market.structure_levels
    if isinstance(existing, dict):
        structure_levels = dict(existing)
    else:
        structure_levels = {}
    structure_levels[EMBEDDED_EVIDENCE_KEY] = _serialize_evidence_snapshot(evidence)

    updated_market = replace(snapshot.market, structure_levels=structure_levels)
    get_observability().log_embed_decision(
        symbol=evidence.symbol,
        engine_timestamp_ms=evidence.engine_timestamp_ms,
        opinion_count=opinion_count,
        written=True,
    )
    return replace(snapshot, market=updated_market)
