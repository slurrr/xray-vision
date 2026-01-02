import unittest

from regime_engine.contracts.regimes import Regime
from regime_engine.explainability.permissions import permissions_for_regime


class TestPermissions(unittest.TestCase):
    def test_permissions_are_static(self) -> None:
        self.assertEqual(permissions_for_regime(Regime.CHOP_BALANCED), ["CHOP_BALANCED"])
        self.assertEqual(permissions_for_regime(Regime.SQUEEZE_UP), ["SQUEEZE_UP"])


if __name__ == "__main__":
    unittest.main()
