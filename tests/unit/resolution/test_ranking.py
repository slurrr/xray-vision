import unittest

from regime_engine.contracts.regimes import Regime, RegimeScore
from regime_engine.resolution.ranking import rank_scores


class TestRanking(unittest.TestCase):
    def test_rank_scores_descending(self) -> None:
        scores = [
            RegimeScore(regime=Regime.SQUEEZE_UP, score=1.0, contributors=[]),
            RegimeScore(regime=Regime.CHOP_BALANCED, score=3.0, contributors=[]),
            RegimeScore(regime=Regime.TREND_BUILD_UP, score=2.0, contributors=[]),
        ]
        ranked = rank_scores(scores)
        self.assertEqual(
            [score.regime for score in ranked],
            [Regime.CHOP_BALANCED, Regime.TREND_BUILD_UP, Regime.SQUEEZE_UP],
        )

    def test_rank_scores_tiebreak_regime_order(self) -> None:
        scores = [
            RegimeScore(regime=Regime.SQUEEZE_UP, score=1.0, contributors=[]),
            RegimeScore(regime=Regime.CHOP_BALANCED, score=1.0, contributors=[]),
            RegimeScore(regime=Regime.TREND_BUILD_UP, score=1.0, contributors=[]),
        ]
        ranked = rank_scores(scores)
        self.assertEqual(
            [score.regime for score in ranked],
            [Regime.CHOP_BALANCED, Regime.SQUEEZE_UP, Regime.TREND_BUILD_UP],
        )


if __name__ == "__main__":
    unittest.main()
