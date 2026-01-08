from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from regime_engine.contracts.regimes import Regime
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot
from regime_engine.state.invariants import assert_belief_invariants
from regime_engine.state.state import SCHEMA_NAME, SCHEMA_VERSION, RegimeState

_REGIME_ORDER = tuple(Regime)
_REGIME_INDEX = {regime: index for index, regime in enumerate(_REGIME_ORDER)}


def _uniform_belief() -> Mapping[Regime, float]:
    regimes = _REGIME_ORDER
    if not regimes:
        return MappingProxyType({})
    weight = 1.0 / len(regimes)
    return MappingProxyType({regime: weight for regime in regimes})


def initialize_state(*, symbol: str, engine_timestamp_ms: int) -> RegimeState:
    beliefs = _uniform_belief()
    anchor = _REGIME_ORDER[0]
    state = RegimeState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        belief_by_regime=beliefs,
        anchor_regime=anchor,
    )
    assert_belief_invariants(state)
    return state


def _select_opinion(opinions: Iterable[EvidenceOpinion]) -> EvidenceOpinion | None:
    ordered = sorted(
        opinions,
        key=lambda opinion: (
            -opinion.strength,
            -opinion.confidence,
            _REGIME_INDEX[opinion.regime],
        ),
    )
    return ordered[0] if ordered else None


def update_belief(state: RegimeState, evidence: EvidenceSnapshot) -> RegimeState:
    if state.symbol != evidence.symbol:
        raise ValueError("evidence symbol must match state symbol")

    selected = _select_opinion(evidence.opinions)
    if selected is None:
        updated = RegimeState(
            schema=SCHEMA_NAME,
            schema_version=SCHEMA_VERSION,
            symbol=state.symbol,
            engine_timestamp_ms=evidence.engine_timestamp_ms,
            belief_by_regime=state.belief_by_regime,
            anchor_regime=state.anchor_regime,
        )
        assert_belief_invariants(updated)
        return updated

    beliefs = {regime: 1.0 if regime == selected.regime else 0.0 for regime in _REGIME_ORDER}
    updated = RegimeState(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol=state.symbol,
        engine_timestamp_ms=evidence.engine_timestamp_ms,
        belief_by_regime=MappingProxyType(beliefs),
        anchor_regime=selected.regime,
    )
    assert_belief_invariants(updated)
    return updated


def project_regime(state: RegimeState) -> Regime:
    ordered = sorted(
        state.belief_by_regime.items(),
        key=lambda item: (-item[1], _REGIME_INDEX[item[0]]),
    )
    return ordered[0][0]
