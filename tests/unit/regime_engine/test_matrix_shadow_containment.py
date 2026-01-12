import unittest
from collections.abc import Mapping

from regime_engine.contracts.snapshots import (
    ContextSnapshot,
    DerivativesSnapshot,
    FlowSnapshot,
    MarketSnapshot,
    RegimeInputSnapshot,
)
from regime_engine.observability import Observability, get_observability, set_observability
from regime_engine.pipeline import run_pipeline_with_state


class _MatrixRaisingLogger:
    def log(self, level: int, message: str, fields: Mapping[str, object]) -> None:
        if message.startswith("regime_engine.matrix."):
            raise RuntimeError("logger failure")
        return None

    def is_enabled_for(self, level: int) -> bool:
        return True


class _FailingInterpreter:
    def interpret(self, evidence: object) -> object:
        raise RuntimeError("interpreter failure")


def _make_snapshot() -> RegimeInputSnapshot:
    return RegimeInputSnapshot(
        symbol="TEST",
        timestamp=180_000,
        market=MarketSnapshot(
            price=1.0,
            vwap=1.0,
            atr=1.0,
            atr_z=0.0,
            range_expansion=0.0,
            structure_levels={},
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


class TestMatrixShadowContainment(unittest.TestCase):
    def test_shadow_logging_failure_is_contained(self) -> None:
        prior_observability = get_observability()
        try:
            set_observability(Observability(logger=_MatrixRaisingLogger()))
            output, _state = run_pipeline_with_state(_make_snapshot())
            self.assertEqual(output.symbol, "TEST")
        finally:
            set_observability(prior_observability)

    def test_shadow_interpreter_and_logging_failures_are_contained(self) -> None:
        prior_observability = get_observability()
        try:
            set_observability(Observability(logger=_MatrixRaisingLogger()))
            import regime_engine.pipeline as pipeline

            prior_interpreter = pipeline._MATRIX_INTERPRETER
            pipeline._MATRIX_INTERPRETER = _FailingInterpreter()
            try:
                output, _state = run_pipeline_with_state(_make_snapshot())
                self.assertEqual(output.symbol, "TEST")
            finally:
                pipeline._MATRIX_INTERPRETER = prior_interpreter
        finally:
            set_observability(prior_observability)


if __name__ == "__main__":
    unittest.main()
