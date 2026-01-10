from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from composer.contracts.feature_snapshot import FeatureSnapshot, feature_value
from regime_engine.contracts.regimes import Regime
from regime_engine.state.evidence import EvidenceOpinion


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return False


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    return None


def clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def availability_confidence(
    features: Mapping[str, float | None],
    required_keys: Sequence[str],
) -> float:
    required_count = len(required_keys)
    if required_count == 0:
        return 0.0
    available = 0
    for key in required_keys:
        value = feature_value(features, key)
        if value is not None and _is_finite_number(value):
            available += 1
    return available / required_count


def flow_ratio(features: Mapping[str, float | None]) -> float | None:
    cvd = _as_float(feature_value(features, "cvd"))
    open_interest = _as_float(feature_value(features, "open_interest"))
    if cvd is None or open_interest is None:
        return None
    if open_interest <= 0.0:
        return None
    return cvd / open_interest


def trend_sign(features: Mapping[str, float | None]) -> int | None:
    price = _as_float(feature_value(features, "price"))
    vwap = _as_float(feature_value(features, "vwap"))
    if price is None or vwap is None:
        return None
    if price > vwap:
        return 1
    if price < vwap:
        return -1
    return 0


def _pick_by_regime_order(scores: Mapping[Regime, float]) -> tuple[Regime, float]:
    best_regime = next(iter(Regime))
    best_score = -1.0
    for regime in Regime:
        score = scores.get(regime, 0.0)
        if score > best_score:
            best_regime = regime
            best_score = score
    return best_regime, best_score


@dataclass(frozen=True)
class EngineEvidenceObserver:
    observer_id: str
    source_id: str

    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        raise NotImplementedError


class ClassicalRegimeObserver(EngineEvidenceObserver):
    _confidence_keys = ("price", "vwap", "atr_z", "cvd", "open_interest")

    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        features = snapshot.features
        vol = _as_float(feature_value(features, "atr_z"))
        fr = flow_ratio(features)
        ts = trend_sign(features)

        abs_fr = abs(fr) if fr is not None else 0.0
        vol_level = clamp01((vol + 1.0) / 3.0) if vol is not None else 0.0
        high_vol = clamp01((vol - 1.0) / 2.0) if vol is not None else 0.0

        low_flow = clamp01(1.0 - (abs_fr / 0.01))
        med_flow = clamp01(abs_fr / 0.02)
        high_flow = clamp01(abs_fr / 0.05)

        scores = {
            Regime.CHOP_BALANCED: clamp01((1.0 - vol_level) * low_flow),
            Regime.CHOP_STOPHUNT: clamp01(vol_level * low_flow),
            Regime.LIQUIDATION_UP: clamp01(
                high_vol * high_flow * (1.0 if fr is not None and fr > 0 else 0.0)
            ),
            Regime.LIQUIDATION_DOWN: clamp01(
                high_vol * high_flow * (1.0 if fr is not None and fr < 0 else 0.0)
            ),
            Regime.SQUEEZE_UP: clamp01(
                high_vol * med_flow * (1.0 if ts is not None and ts > 0 else 0.0)
            ),
            Regime.SQUEEZE_DOWN: clamp01(
                high_vol * med_flow * (1.0 if ts is not None and ts < 0 else 0.0)
            ),
            Regime.TREND_BUILD_UP: clamp01(
                vol_level * med_flow * (1.0 if ts is not None and ts > 0 else 0.0)
            ),
            Regime.TREND_BUILD_DOWN: clamp01(
                vol_level * med_flow * (1.0 if ts is not None and ts < 0 else 0.0)
            ),
            Regime.TREND_EXHAUSTION: clamp01(high_vol * low_flow),
        }
        winner, score = _pick_by_regime_order(scores)
        confidence = availability_confidence(features, self._confidence_keys)
        return (
            EvidenceOpinion(
                regime=winner,
                strength=clamp01(score),
                confidence=clamp01(confidence),
                source=self.source_id,
            ),
        )


class FlowPressureObserver(EngineEvidenceObserver):
    _confidence_keys = ("cvd", "open_interest")

    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        features = snapshot.features
        fr = flow_ratio(features)
        if fr is None or abs(fr) < 0.002:
            return ()

        direction_up = fr > 0
        vol = _as_float(feature_value(features, "atr_z"))

        if vol is not None and vol >= 1.5 and abs(fr) >= 0.02:
            regime = Regime.LIQUIDATION_UP if direction_up else Regime.LIQUIDATION_DOWN
        elif vol is not None and vol >= 1.0:
            regime = Regime.SQUEEZE_UP if direction_up else Regime.SQUEEZE_DOWN
        else:
            regime = Regime.TREND_BUILD_UP if direction_up else Regime.TREND_BUILD_DOWN

        confidence = availability_confidence(features, self._confidence_keys)
        strength = clamp01(abs(fr) / 0.02)
        return (
            EvidenceOpinion(
                regime=regime,
                strength=strength,
                confidence=clamp01(confidence),
                source=self.source_id,
            ),
        )


class VolatilityContextObserver(EngineEvidenceObserver):
    _confidence_keys = ("atr_z",)

    def emit(self, snapshot: FeatureSnapshot) -> Sequence[EvidenceOpinion]:
        features = snapshot.features
        vol = _as_float(feature_value(features, "atr_z"))
        if vol is None:
            return ()

        regime: Regime | None
        if vol <= 0.2:
            regime = Regime.CHOP_BALANCED
        elif vol <= 0.8:
            regime = Regime.CHOP_STOPHUNT
        elif vol >= 1.8:
            regime = Regime.TREND_EXHAUSTION
        else:
            ts = trend_sign(features)
            if ts is None or ts == 0:
                return ()
            regime = Regime.SQUEEZE_UP if ts > 0 else Regime.SQUEEZE_DOWN

        confidence = availability_confidence(features, self._confidence_keys)
        strength = clamp01((vol - 0.2) / 2.0)
        return (
            EvidenceOpinion(
                regime=regime,
                strength=strength,
                confidence=clamp01(confidence),
                source=self.source_id,
            ),
        )


OBSERVERS_V1: Sequence[EngineEvidenceObserver] = (
    ClassicalRegimeObserver(
        observer_id="classical_regime_v1",
        source_id="composer:classical_regime_v1",
    ),
    FlowPressureObserver(
        observer_id="flow_pressure_v1",
        source_id="composer:flow_pressure_v1",
    ),
    VolatilityContextObserver(
        observer_id="volatility_context_v1",
        source_id="composer:volatility_context_v1",
    ),
)
