from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from importlib import resources

from regime_engine.contracts.regimes import Regime
from regime_engine.matrix.definitions.types_v1 import (
    CellDefinition,
    MatrixDefinitionV1,
    MatrixWeights,
    SourceDefaults,
)

_ROOT_KEYS = {"defaults", "sources", "cells"}
_WEIGHT_KEYS = {"strength_weight", "confidence_weight", "strength_cap", "confidence_cap"}
_SOURCE_KEYS = {"source", "strength_weight", "confidence_weight", "strength_cap", "confidence_cap"}
_CELL_KEYS = {
    "source",
    "type",
    "direction",
    "regime",
    "strength_weight",
    "confidence_weight",
    "strength_cap",
    "confidence_cap",
}
_ALLOWED_DIRECTIONS = {"UP", "DOWN", "NEUTRAL"}


def load_definition_v1() -> MatrixDefinitionV1:
    payload = _load_payload()
    return _parse_definition(payload)


def _load_payload() -> Mapping[str, object]:
    text = (
        resources.files("regime_engine.matrix.definitions")
        .joinpath("v1.yaml")
        .read_text(encoding="utf-8")
    )
    yaml = importlib.import_module("yaml")
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("matrix definition v1 must be a mapping")
    return data


def _parse_definition(payload: Mapping[str, object]) -> MatrixDefinitionV1:
    _reject_unknown(payload, _ROOT_KEYS, "matrix definition")
    defaults_raw = payload.get("defaults")
    if not isinstance(defaults_raw, Mapping):
        raise ValueError("matrix defaults must be a mapping")
    defaults = _parse_defaults(defaults_raw)
    sources_raw = payload.get("sources") or []
    cells_raw = payload.get("cells") or []
    sources = _parse_sources(sources_raw, defaults=defaults)
    cells = _parse_cells(cells_raw, defaults=defaults, source_defaults=sources)
    return MatrixDefinitionV1(
        defaults=defaults,
        source_defaults=tuple(sources),
        cells=tuple(cells),
    )

def _parse_sources(
    items: object, *, defaults: MatrixWeights
) -> tuple[SourceDefaults, ...]:
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValueError("matrix sources must be a list")
    parsed: list[SourceDefaults] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("matrix source entry must be a mapping")
        _reject_unknown(item, _SOURCE_KEYS, "matrix source")
        source = item.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("matrix source must be a non-empty string")
        if source in seen:
            raise ValueError(f"duplicate matrix source: {source}")
        seen.add(source)
        weights = _parse_weights(item, defaults=defaults, label=f"source:{source}")
        parsed.append(SourceDefaults(source=source, weights=weights))
    return tuple(sorted(parsed, key=lambda entry: entry.source))

def _parse_cells(
    items: object,
    *,
    defaults: MatrixWeights,
    source_defaults: Sequence[SourceDefaults],
) -> tuple[CellDefinition, ...]:
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ValueError("matrix cells must be a list")
    parsed: list[CellDefinition] = []
    source_weights = {entry.source: entry.weights for entry in source_defaults}
    seen: set[tuple[str, str, str, Regime]] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("matrix cell entry must be a mapping")
        _reject_unknown(item, _CELL_KEYS, "matrix cell")
        source = item.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError("matrix cell source must be a non-empty string")
        evidence_type = item.get("type")
        if not isinstance(evidence_type, str) or not evidence_type:
            raise ValueError("matrix cell type must be a non-empty string")
        direction = item.get("direction")
        if not isinstance(direction, str) or direction not in _ALLOWED_DIRECTIONS:
            raise ValueError("matrix cell direction must be UP, DOWN, or NEUTRAL")
        regime = _parse_regime(item.get("regime"))
        key = (source, evidence_type, direction, regime)
        if key in seen:
            raise ValueError(
                f"duplicate matrix cell: {source}:{evidence_type}:{direction}:{regime.value}"
            )
        seen.add(key)
        weights = _parse_weights(
            item,
            defaults=source_weights.get(source, defaults),
            label=f"cell:{source}:{evidence_type}:{direction}:{regime.value}",
        )
        parsed.append(
            CellDefinition(
                source=source,
                evidence_type=evidence_type,
                direction=direction,
                regime=regime,
                weights=weights,
            )
        )
    return tuple(
        sorted(
            parsed,
            key=lambda entry: (
                entry.source,
                entry.evidence_type,
                entry.direction,
                entry.regime.value,
            ),
        )
    )


def _parse_weights(
    payload: Mapping[str, object],
    *,
    defaults: MatrixWeights,
    label: str,
) -> MatrixWeights:
    _reject_unknown(payload, _WEIGHT_KEYS | {"source", "regime", "type", "direction"}, label)
    strength_weight = _parse_optional_unit(
        payload.get("strength_weight"), defaults.strength_weight, f"{label}.strength_weight"
    )
    confidence_weight = _parse_optional_unit(
        payload.get("confidence_weight"),
        defaults.confidence_weight,
        f"{label}.confidence_weight",
    )
    strength_cap = _parse_optional_cap(
        payload.get("strength_cap"), defaults.strength_cap, f"{label}.strength_cap"
    )
    confidence_cap = _parse_optional_cap(
        payload.get("confidence_cap"),
        defaults.confidence_cap,
        f"{label}.confidence_cap",
    )
    return MatrixWeights(
        strength_weight=strength_weight,
        confidence_weight=confidence_weight,
        strength_cap=strength_cap,
        confidence_cap=confidence_cap,
    )


def _parse_defaults(payload: Mapping[str, object]) -> MatrixWeights:
    _reject_unknown(payload, _WEIGHT_KEYS, "defaults")
    strength_weight = _parse_required_unit(
        payload.get("strength_weight"), "defaults.strength_weight"
    )
    confidence_weight = _parse_required_unit(
        payload.get("confidence_weight"), "defaults.confidence_weight"
    )
    strength_cap = _parse_optional_cap(
        payload.get("strength_cap"), None, "defaults.strength_cap"
    )
    confidence_cap = _parse_optional_cap(
        payload.get("confidence_cap"), None, "defaults.confidence_cap"
    )
    return MatrixWeights(
        strength_weight=strength_weight,
        confidence_weight=confidence_weight,
        strength_cap=strength_cap,
        confidence_cap=confidence_cap,
    )


def _parse_optional_unit(value: object, default: float, label: str) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not 0.0 <= float(value) <= 1.0:
        raise ValueError(f"{label} must be between 0 and 1")
    return float(value)


def _parse_optional_cap(value: object, default: float | None, label: str) -> float | None:
    if value is None:
        return default
    return _parse_optional_unit(value, 0.0, label)


def _parse_required_unit(value: object, label: str) -> float:
    if value is None:
        raise ValueError(f"{label} is required")
    return _parse_optional_unit(value, 0.0, label)


def _parse_regime(value: object) -> Regime:
    if not isinstance(value, str):
        raise ValueError("matrix cell regime must be a string")
    for regime in Regime:
        if regime.value == value:
            return regime
    raise ValueError(f"unknown regime value: {value}")


def _reject_unknown(payload: Mapping[str, object], allowed: set[str], label: str) -> None:
    unknown = set(payload.keys()) - allowed
    if unknown:
        unknown_list = ", ".join(sorted(str(item) for item in unknown))
        raise ValueError(f"unknown {label} keys: {unknown_list}")
