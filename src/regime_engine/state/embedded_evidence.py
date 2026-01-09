from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import RegimeInputSnapshot
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot

EMBEDDED_EVIDENCE_KEY = "composer_evidence_snapshot_v1"

INVALIDATION_INVALID_FIELDS = "INVALID_EVIDENCE_FIELDS"
INVALIDATION_INVALID_BOUNDS = "INVALID_EVIDENCE_BOUNDS"
INVALIDATION_UNKNOWN_REGIME = "INVALID_EVIDENCE_REGIME"
INVALIDATION_SYMBOL_MISMATCH = "INVALID_EVIDENCE_SYMBOL_MISMATCH"
INVALIDATION_TIMESTAMP_MISMATCH = "INVALID_EVIDENCE_TIMESTAMP_MISMATCH"


@dataclass(frozen=True)
class EmbeddedEvidenceResult:
    evidence: EvidenceSnapshot
    drivers: list[str]
    invalidations: list[str]


def extract_embedded_evidence(
    snapshot: RegimeInputSnapshot,
) -> EmbeddedEvidenceResult | None:
    payload = _read_embedded_payload(snapshot)
    if payload is None:
        return None

    symbol = payload.get("symbol")
    timestamp = payload.get("engine_timestamp_ms")
    invalidations: list[str] = []
    if symbol != snapshot.symbol:
        invalidations.append(INVALIDATION_SYMBOL_MISMATCH)
    if timestamp != snapshot.timestamp:
        invalidations.append(INVALIDATION_TIMESTAMP_MISMATCH)
    if invalidations:
        evidence = EvidenceSnapshot(
            symbol=snapshot.symbol,
            engine_timestamp_ms=snapshot.timestamp,
            opinions=(),
        )
        return EmbeddedEvidenceResult(
            evidence=evidence,
            drivers=["DRIVER_NO_CANONICAL_EVIDENCE"],
            invalidations=_unique_ordered(invalidations),
        )

    opinions_payload = payload.get("opinions")
    opinions = _parse_opinions(opinions_payload, invalidations)
    ordered = tuple(_order_opinions(opinions))
    evidence = EvidenceSnapshot(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
        opinions=ordered,
    )
    if ordered:
        drivers = _drivers_from_sources(ordered)
    else:
        drivers = ["DRIVER_NO_CANONICAL_EVIDENCE"]
    return EmbeddedEvidenceResult(
        evidence=evidence,
        drivers=drivers,
        invalidations=_unique_ordered(invalidations),
    )


def _read_embedded_payload(snapshot: RegimeInputSnapshot) -> Mapping[str, object] | None:
    structure_levels = snapshot.market.structure_levels
    if not isinstance(structure_levels, Mapping):
        return None
    payload = structure_levels.get(EMBEDDED_EVIDENCE_KEY)
    if not isinstance(payload, Mapping):
        return None
    return payload


def _parse_opinions(
    payload: object,
    invalidations: list[str],
) -> list[EvidenceOpinion]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return []
    opinions: list[EvidenceOpinion] = []
    for item in payload:
        opinion = _parse_opinion(item, invalidations)
        if opinion is not None:
            opinions.append(opinion)
    return opinions


def _parse_opinion(
    payload: object,
    invalidations: list[str],
) -> EvidenceOpinion | None:
    if not isinstance(payload, Mapping):
        invalidations.append(INVALIDATION_INVALID_FIELDS)
        return None

    regime_value = payload.get("regime")
    source_value = payload.get("source")
    strength_value = payload.get("strength")
    confidence_value = payload.get("confidence")

    if not isinstance(regime_value, str) or not isinstance(source_value, str):
        invalidations.append(INVALIDATION_INVALID_FIELDS)
        return None
    regime = _regime_from_value(regime_value)
    if regime is None:
        invalidations.append(INVALIDATION_UNKNOWN_REGIME)
        return None

    strength = _as_bounded_float(strength_value)
    confidence = _as_bounded_float(confidence_value)
    if strength is None or confidence is None:
        invalidations.append(INVALIDATION_INVALID_BOUNDS)
        return None

    return EvidenceOpinion(
        regime=regime,
        strength=strength,
        confidence=confidence,
        source=source_value,
    )


def _regime_from_value(value: str) -> Regime | None:
    for regime in Regime:
        if regime.value == value:
            return regime
    return None


def _as_bounded_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value):
        return None
    if value < 0.0 or value > 1.0:
        return None
    return float(value)


def _order_opinions(opinions: Sequence[EvidenceOpinion]) -> list[EvidenceOpinion]:
    return sorted(
        opinions,
        key=lambda opinion: (
            opinion.regime.value,
            opinion.source,
            -opinion.confidence,
            -opinion.strength,
        ),
    )


def _drivers_from_sources(opinions: Sequence[EvidenceOpinion]) -> list[str]:
    drivers: list[str] = []
    seen: set[str] = set()
    for opinion in opinions:
        if opinion.source in seen:
            continue
        seen.add(opinion.source)
        drivers.append(opinion.source)
    return drivers


def _unique_ordered(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
