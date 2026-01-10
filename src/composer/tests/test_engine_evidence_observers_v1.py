import unittest
from types import MappingProxyType

from composer.contracts.feature_snapshot import (
    FEATURE_KEYS_V1,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    FeatureSnapshot,
)
from composer.engine_evidence import (
    EMBEDDED_EVIDENCE_KEY,
    compute_engine_evidence_snapshot,
    embed_engine_evidence,
)
from composer.engine_evidence.observers import (
    ClassicalRegimeObserver,
    FlowPressureObserver,
    VolatilityContextObserver,
)
from composer.engine_evidence.ordering import order_engine_evidence_opinions
from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.state.evidence import EvidenceOpinion, EvidenceSnapshot


def _feature_snapshot(values: dict[str, float | None]) -> FeatureSnapshot:
    features = {key: values.get(key) for key in FEATURE_KEYS_V1}
    return FeatureSnapshot(
        schema=SCHEMA_NAME,
        schema_version=SCHEMA_VERSION,
        symbol="TEST",
        engine_timestamp_ms=180_000,
        features=MappingProxyType(features),
    )


class TestEngineEvidenceObservers(unittest.TestCase):
    def test_classical_regime_confidence_zero_with_missing_inputs(self) -> None:
        observer = ClassicalRegimeObserver(
            observer_id="classical_regime_v1",
            source_id="composer:classical_regime_v1",
        )
        snapshot = _feature_snapshot({})
        opinions = observer.emit(snapshot)
        self.assertEqual(len(opinions), 1)
        self.assertAlmostEqual(opinions[0].confidence, 0.0)

    def test_classical_regime_confidence_ratio(self) -> None:
        observer = ClassicalRegimeObserver(
            observer_id="classical_regime_v1",
            source_id="composer:classical_regime_v1",
        )
        snapshot = _feature_snapshot({"price_last": 2.0, "vwap_3m": 1.0})
        opinions = observer.emit(snapshot)
        self.assertEqual(len(opinions), 1)
        self.assertAlmostEqual(opinions[0].confidence, 0.4)

    def test_classical_regime_emits_one(self) -> None:
        observer = ClassicalRegimeObserver(
            observer_id="classical_regime_v1",
            source_id="composer:classical_regime_v1",
        )
        snapshot = _feature_snapshot(
            {
                "price_last": 2.0,
                "vwap_3m": 1.0,
                "atr_z_50": 2.0,
                "cvd_3m": 10.0,
                "open_interest_latest": 1000.0,
            }
        )
        opinions = observer.emit(snapshot)
        self.assertEqual(len(opinions), 1)
        opinion = opinions[0]
        self.assertEqual(opinion.regime, Regime.TREND_BUILD_UP)
        self.assertEqual(opinion.source, "composer:classical_regime_v1")
        self.assertAlmostEqual(opinion.confidence, 1.0)
        self.assertAlmostEqual(opinion.strength, 0.5)

    def test_flow_pressure_emits_none_when_small(self) -> None:
        observer = FlowPressureObserver(
            observer_id="flow_pressure_v1",
            source_id="composer:flow_pressure_v1",
        )
        snapshot = _feature_snapshot({"cvd_3m": 1.0, "open_interest_latest": 1000.0})
        self.assertEqual(observer.emit(snapshot), ())

    def test_flow_pressure_liquidation(self) -> None:
        observer = FlowPressureObserver(
            observer_id="flow_pressure_v1",
            source_id="composer:flow_pressure_v1",
        )
        snapshot = _feature_snapshot(
            {"cvd_3m": 10.0, "open_interest_latest": 100.0, "atr_z_50": 2.0}
        )
        opinions = observer.emit(snapshot)
        self.assertEqual(len(opinions), 1)
        opinion = opinions[0]
        self.assertEqual(opinion.regime, Regime.LIQUIDATION_UP)
        self.assertAlmostEqual(opinion.strength, 1.0)
        self.assertAlmostEqual(opinion.confidence, 1.0)

    def test_volatility_context_emits_balanced(self) -> None:
        observer = VolatilityContextObserver(
            observer_id="volatility_context_v1",
            source_id="composer:volatility_context_v1",
        )
        snapshot = _feature_snapshot({"atr_z_50": 0.1})
        opinions = observer.emit(snapshot)
        self.assertEqual(len(opinions), 1)
        opinion = opinions[0]
        self.assertEqual(opinion.regime, Regime.CHOP_BALANCED)
        self.assertAlmostEqual(opinion.strength, 0.0)
        self.assertAlmostEqual(opinion.confidence, 1.0)

    def test_ordering_is_deterministic(self) -> None:
        snapshot = _feature_snapshot(
            {
                "price_last": 2.0,
                "vwap_3m": 1.0,
                "atr_z_50": 2.0,
                "cvd_3m": 10.0,
                "open_interest_latest": 100.0,
            }
        )
        evidence = compute_engine_evidence_snapshot(snapshot)
        ordered = order_engine_evidence_opinions(evidence.opinions)
        self.assertEqual(tuple(ordered), evidence.opinions)

    def test_ordering_is_stable_for_shuffled_inputs(self) -> None:
        opinions = [
            EvidenceOpinion(
                regime=Regime.TREND_BUILD_UP,
                strength=0.2,
                confidence=0.4,
                source="b",
            ),
            EvidenceOpinion(
                regime=Regime.CHOP_BALANCED,
                strength=0.9,
                confidence=0.1,
                source="a",
            ),
            EvidenceOpinion(
                regime=Regime.CHOP_BALANCED,
                strength=0.5,
                confidence=0.9,
                source="a",
            ),
        ]
        ordered = order_engine_evidence_opinions(opinions)
        self.assertEqual(
            [opinion.regime for opinion in ordered],
            [Regime.CHOP_BALANCED, Regime.CHOP_BALANCED, Regime.TREND_BUILD_UP],
        )
        self.assertEqual(
            [opinion.confidence for opinion in ordered[:2]],
            [0.9, 0.1],
        )

    def test_embedding_omits_empty(self) -> None:
        evidence = EvidenceSnapshot(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            opinions=(),
        )
        snapshot = _make_snapshot(structure_levels={})
        embedded = embed_engine_evidence(snapshot, evidence)
        self.assertNotIn(EMBEDDED_EVIDENCE_KEY, embedded.market.structure_levels)

    def test_embedding_inserts_payload(self) -> None:
        snapshot = _feature_snapshot(
            {
                "price_last": 2.0,
                "vwap_3m": 1.0,
                "atr_z_50": 2.0,
                "cvd_3m": 10.0,
                "open_interest_latest": 100.0,
            }
        )
        evidence = compute_engine_evidence_snapshot(snapshot)
        legacy_snapshot = _make_snapshot(structure_levels={"existing": 1})
        embedded = embed_engine_evidence(legacy_snapshot, evidence)
        payload = embedded.market.structure_levels[EMBEDDED_EVIDENCE_KEY]
        self.assertEqual(payload["symbol"], "TEST")
        self.assertEqual(payload["engine_timestamp_ms"], 180_000)
        self.assertIsInstance(payload["opinions"], list)
        self.assertIn("existing", embedded.market.structure_levels)


def _make_snapshot(*, structure_levels: dict[str, object]) -> RegimeInputSnapshot:
    return RegimeInputSnapshot(
        symbol="TEST",
        timestamp=180_000,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
            range_expansion=0.0,
            structure_levels=structure_levels,
            acceptance_score=0.0,
            sweep_score=0.0,
        ),
        derivatives=DerivativesSnapshot(
            open_interest=1.0,
            oi_slope_short=0.0,
            oi_slope_med=0.0,
            oi_accel=0.0,
            funding_rate=0.0,
            funding_slope=0.0,
            funding_z=0.0,
            liquidation_intensity=None,
        ),
        flow=FlowSnapshot(
            cvd=0.0,
            cvd_slope=0.0,
            cvd_efficiency=0.0,
            aggressive_volume_ratio=0.0,
        ),
        context=ContextSnapshot(
            rs_vs_btc=0.0,
            beta_to_btc=0.0,
            alt_breadth=0.0,
            btc_regime=None,
            eth_regime=None,
        ),
    )


if __name__ == "__main__":
    unittest.main()
