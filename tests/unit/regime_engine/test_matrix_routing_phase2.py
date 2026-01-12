import os
import unittest
from unittest.mock import patch

from regime_engine.contracts.regimes import Regime
from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.matrix.types import RegimeInfluence, RegimeInfluenceSet
from regime_engine.pipeline import run_pipeline_with_state
from regime_engine.state.embedded_evidence import EMBEDDED_EVIDENCE_KEY


class _FixedInterpreter:
    def __init__(self, influence_set: RegimeInfluenceSet) -> None:
        self._influence_set = influence_set

    def interpret(self, evidence: object) -> RegimeInfluenceSet:
        return self._influence_set


def _make_snapshot() -> RegimeInputSnapshot:
    payload = {
        "symbol": "TEST",
        "engine_timestamp_ms": 180_000,
        "opinions": [
            {
                "regime": Regime.CHOP_BALANCED.value,
                "strength": 0.9,
                "confidence": 0.8,
                "source": "composer:test",
            }
        ],
    }
    return RegimeInputSnapshot(
        symbol="TEST",
        timestamp=180_000,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
            range_expansion=0.0,
            structure_levels={EMBEDDED_EVIDENCE_KEY: payload},
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


def _matrix_influence_set(
    *,
    symbol: str,
    engine_timestamp_ms: int,
    regime: Regime,
    strength: float,
    confidence: float,
    source: str,
) -> RegimeInfluenceSet:
    return RegimeInfluenceSet(
        symbol=symbol,
        engine_timestamp_ms=engine_timestamp_ms,
        influences=(
            RegimeInfluence(
                regime=regime,
                strength=strength,
                confidence=confidence,
                source=source,
            ),
        ),
    )


class TestMatrixRoutingPhase2(unittest.TestCase):
    def test_dual_run_keeps_legacy_belief(self) -> None:
        snapshot = _make_snapshot()
        influence_set = _matrix_influence_set(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            regime=Regime.TREND_BUILD_UP,
            strength=1.0,
            confidence=1.0,
            source="matrix:test",
        )
        import regime_engine.pipeline as pipeline

        prior_interpreter = pipeline._MATRIX_INTERPRETER
        pipeline._MATRIX_INTERPRETER = _FixedInterpreter(influence_set)
        try:
            with patch.dict(
                os.environ,
                {
                    "REGIME_ENGINE_MATRIX_MODE": "dual_run",
                    "REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST": "TEST",
                },
                clear=False,
            ):
                _output, state = run_pipeline_with_state(snapshot)
                self.assertEqual(state.anchor_regime, Regime.CHOP_BALANCED)
        finally:
            pipeline._MATRIX_INTERPRETER = prior_interpreter

    def test_matrix_enabled_uses_matrix_belief(self) -> None:
        snapshot = _make_snapshot()
        influence_set = _matrix_influence_set(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            regime=Regime.TREND_BUILD_UP,
            strength=1.0,
            confidence=1.0,
            source="matrix:test",
        )
        import regime_engine.pipeline as pipeline

        prior_interpreter = pipeline._MATRIX_INTERPRETER
        pipeline._MATRIX_INTERPRETER = _FixedInterpreter(influence_set)
        try:
            with patch.dict(
                os.environ,
                {
                    "REGIME_ENGINE_MATRIX_MODE": "matrix_enabled",
                    "REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST": "TEST",
                },
                clear=False,
            ):
                _output, state = run_pipeline_with_state(snapshot)
                self.assertEqual(state.anchor_regime, Regime.TREND_BUILD_UP)
        finally:
            pipeline._MATRIX_INTERPRETER = prior_interpreter

    def test_matrix_enabled_falls_back_on_bridge_failure(self) -> None:
        snapshot = _make_snapshot()
        influence_set = _matrix_influence_set(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            regime=Regime.TREND_BUILD_UP,
            strength=2.0,
            confidence=1.0,
            source="matrix:test",
        )
        import regime_engine.pipeline as pipeline

        prior_interpreter = pipeline._MATRIX_INTERPRETER
        pipeline._MATRIX_INTERPRETER = _FixedInterpreter(influence_set)
        try:
            with patch.dict(
                os.environ,
                {
                    "REGIME_ENGINE_MATRIX_MODE": "matrix_enabled",
                    "REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST": "TEST",
                },
                clear=False,
            ):
                _output, state = run_pipeline_with_state(snapshot)
                self.assertEqual(state.anchor_regime, Regime.CHOP_BALANCED)
        finally:
            pipeline._MATRIX_INTERPRETER = prior_interpreter

    def test_matrix_enabled_out_of_scope_uses_legacy(self) -> None:
        snapshot = _make_snapshot()
        influence_set = _matrix_influence_set(
            symbol="TEST",
            engine_timestamp_ms=180_000,
            regime=Regime.TREND_BUILD_UP,
            strength=1.0,
            confidence=1.0,
            source="matrix:test",
        )
        import regime_engine.pipeline as pipeline

        prior_interpreter = pipeline._MATRIX_INTERPRETER
        pipeline._MATRIX_INTERPRETER = _FixedInterpreter(influence_set)
        try:
            with patch.dict(
                os.environ,
                {
                    "REGIME_ENGINE_MATRIX_MODE": "matrix_enabled",
                    "REGIME_ENGINE_MATRIX_SYMBOL_ALLOWLIST": "OTHER",
                },
                clear=False,
            ):
                _output, state = run_pipeline_with_state(snapshot)
                self.assertEqual(state.anchor_regime, Regime.CHOP_BALANCED)
        finally:
            pipeline._MATRIX_INTERPRETER = prior_interpreter


if __name__ == "__main__":
    unittest.main()
