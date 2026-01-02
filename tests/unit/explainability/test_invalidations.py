import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.explainability.invalidations import invalidations_from_vetoes
from regime_engine.veto.types import VetoResult


class TestInvalidations(unittest.TestCase):
    def test_includes_only_vetoed_preserves_order_and_dedupes(self) -> None:
        vetoes = [
            VetoResult(
                regime=Regime.CHOP_BALANCED,
                vetoed=False,
                reasons=["acceptance_high_veto_chop"],
            ),
            VetoResult(
                regime=Regime.LIQUIDATION_UP,
                vetoed=True,
                reasons=[
                    "acceptance_high_veto_liquidation",
                    "acceptance_high_veto_liquidation",
                ],
            ),
            VetoResult(
                regime=Regime.TREND_BUILD_UP,
                vetoed=True,
                reasons=["oi_contracting_atr_expanding_veto_trend_build"],
            ),
            VetoResult(
                regime=Regime.TREND_BUILD_DOWN,
                vetoed=True,
                reasons=["oi_contracting_atr_expanding_veto_trend_build"],
            ),
        ]

        invalidations = invalidations_from_vetoes(vetoes)

        self.assertEqual(
            invalidations,
            [
                "acceptance high veto: liquidation",
                "oi contracting + atr expanding veto: trend build",
            ],
        )

    def test_unknown_reason_is_verbatim(self) -> None:
        vetoes = [
            VetoResult(
                regime=Regime.CHOP_BALANCED,
                vetoed=True,
                reasons=["unknown_reason_token"],
            )
        ]
        invalidations = invalidations_from_vetoes(vetoes)
        self.assertEqual(invalidations, ["unknown_reason_token"])


if __name__ == "__main__":
    unittest.main()
