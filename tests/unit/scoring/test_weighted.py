import unittest

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.scoring.types import VetoedScores
from regime_engine.scoring.weighted import apply_weights
from regime_engine.veto.types import VetoResult


class TestWeightedScoring(unittest.TestCase):
    def test_apply_weights_scales_scores(self) -> None:
        vetoed = VetoedScores(
            scores=[
                RegimeScore(regime=Regime.CHOP_BALANCED, score=1.0, contributors=["a"]),
                RegimeScore(regime=Regime.SQUEEZE_UP, score=2.0, contributors=["b"]),
            ],
            vetoes=[VetoResult(regime=Regime.CHOP_BALANCED, vetoed=False, reasons=[])],
        )

        weighted = apply_weights(
            vetoed,
            weights={
                Regime.CHOP_BALANCED: 0.5,
                Regime.SQUEEZE_UP: 2.0,
            },
        )

        self.assertEqual([score.score for score in weighted], [0.5, 4.0])
        self.assertEqual([score.contributors for score in weighted], [["a"], ["b"]])

    def test_apply_weights_defaults_to_one(self) -> None:
        vetoed = VetoedScores(
            scores=[RegimeScore(regime=Regime.CHOP_BALANCED, score=3.0, contributors=[])],
            vetoes=[],
        )

        weighted = apply_weights(vetoed, weights={})
        self.assertEqual(weighted[0].score, 3.0)


if __name__ == "__main__":
    unittest.main()
