from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from regime_engine.contracts.snapshots import RegimeInputSnapshot

EMBEDDED_NEUTRAL_EVIDENCE_KEY = "composer_evidence_snapshot_neutral_v1"

INVALIDATION_INVALID_FIELDS = "INVALID_NEUTRAL_FIELDS"
INVALIDATION_INVALID_BOUNDS = "INVALID_NEUTRAL_BOUNDS"
INVALIDATION_SYMBOL_MISMATCH = "INVALID_NEUTRAL_SYMBOL_MISMATCH"
INVALIDATION_TIMESTAMP_MISMATCH = "INVALID_NEUTRAL_TIMESTAMP_MISMATCH"
INVALIDATION_SCHEMA_MISMATCH = "INVALID_NEUTRAL_SCHEMA"

_EXPECTED_SCHEMA = "evidence_snapshot"
_EXPECTED_SCHEMA_VERSION = "1"
_ALLOWED_DIRECTIONS = {"UP", "DOWN", "NEUTRAL"}


@dataclass(frozen=True)
class NeutralEvidenceOpinion:
    type: str
    direction: str
    strength: float
    confidence: float
    source: str


@dataclass(frozen=True)
class NeutralEvidenceSnapshot:
    symbol: str
    engine_timestamp_ms: int
    opinions: Sequence[NeutralEvidenceOpinion]


@dataclass(frozen=True)
class EmbeddedNeutralEvidenceResult:
    evidence: NeutralEvidenceSnapshot
    invalidations: list[str]


def extract_embedded_neutral_evidence(
    snapshot: RegimeInputSnapshot,
) -> EmbeddedNeutralEvidenceResult | None:
    payload = _read_embedded_payload(snapshot)
    if payload is None:
        return None

    invalidations: list[str] = []
    schema = payload.get("schema")
    schema_version = payload.get("schema_version")
    if schema != _EXPECTED_SCHEMA or schema_version != _EXPECTED_SCHEMA_VERSION:
        invalidations.append(INVALIDATION_SCHEMA_MISMATCH)

    symbol = payload.get("symbol")
    timestamp = payload.get("engine_timestamp_ms")
    if symbol != snapshot.symbol:
        invalidations.append(INVALIDATION_SYMBOL_MISMATCH)
    if timestamp != snapshot.timestamp:
        invalidations.append(INVALIDATION_TIMESTAMP_MISMATCH)

    opinions_payload = payload.get("opinions")
    opinions = _parse_opinions(opinions_payload, invalidations)
    ordered = tuple(_order_opinions(opinions))
    evidence = NeutralEvidenceSnapshot(
        symbol=snapshot.symbol,
        engine_timestamp_ms=snapshot.timestamp,
        opinions=ordered,
    )
    return EmbeddedNeutralEvidenceResult(
        evidence=evidence,
        invalidations=_unique_ordered(invalidations),
    )


def _read_embedded_payload(snapshot: RegimeInputSnapshot) -> Mapping[str, object] | None:
    structure_levels = snapshot.market.structure_levels
    if not isinstance(structure_levels, Mapping):
        return None
    payload = structure_levels.get(EMBEDDED_NEUTRAL_EVIDENCE_KEY)
    if not isinstance(payload, Mapping):
        return None
    return payload


def _parse_opinions(
    payload: object,
    invalidations: list[str],
) -> list[NeutralEvidenceOpinion]:
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
        return []
    opinions: list[NeutralEvidenceOpinion] = []
    for item in payload:
        opinion = _parse_opinion(item, invalidations)
        if opinion is not None:
            opinions.append(opinion)
    return opinions


def _parse_opinion(
    payload: object,
    invalidations: list[str],
) -> NeutralEvidenceOpinion | None:
    if not isinstance(payload, Mapping):
        invalidations.append(INVALIDATION_INVALID_FIELDS)
        return None

    type_value = payload.get("type")
    direction_value = payload.get("direction")
    source_value = payload.get("source")
    strength_value = payload.get("strength")
    confidence_value = payload.get("confidence")

    if (
        not isinstance(type_value, str)
        or not type_value
        or not isinstance(source_value, str)
        or not source_value
    ):
        invalidations.append(INVALIDATION_INVALID_FIELDS)
        return None
    if not isinstance(direction_value, str) or direction_value not in _ALLOWED_DIRECTIONS:
        invalidations.append(INVALIDATION_INVALID_FIELDS)
        return None

    strength = _as_bounded_float(strength_value)
    confidence = _as_bounded_float(confidence_value)
    if strength is None or confidence is None:
        invalidations.append(INVALIDATION_INVALID_BOUNDS)
        return None

    return NeutralEvidenceOpinion(
        type=type_value,
        direction=direction_value,
        strength=strength,
        confidence=confidence,
        source=source_value,
    )


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


def _order_opinions(
    opinions: Sequence[NeutralEvidenceOpinion],
) -> list[NeutralEvidenceOpinion]:
    return sorted(
        opinions,
        key=lambda opinion: (
            opinion.type,
            opinion.source,
            opinion.direction,
            -opinion.strength,
            -opinion.confidence,
        ),
    )


def _unique_ordered(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
