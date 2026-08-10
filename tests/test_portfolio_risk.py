from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fia_public.portfolio_risk import PortfolioRiskError, calculate_portfolio_risk  # noqa: E402


class PortfolioRiskTests(unittest.TestCase):
    def test_ephemeral_calculation_is_deterministic(self) -> None:
        weights = {"AAA": 0.6, "BBB": 0.4}
        returns = {"AAA": [0.01, -0.01, 0.02], "BBB": [0.00, 0.01, -0.01]}
        first = calculate_portfolio_risk(weights, returns)
        second = calculate_portfolio_risk(weights, returns)
        self.assertEqual(first, second)
        self.assertEqual(first["persistence"], "none")
        self.assertAlmostEqual(first["hhi"], 0.52)

    def test_invalid_weights_fail_closed(self) -> None:
        with self.assertRaises(PortfolioRiskError):
            calculate_portfolio_risk(
                {"AAA": 0.8, "BBB": 0.8}, {"AAA": [0.0, 0.1], "BBB": [0.1, 0.0]}
            )


if __name__ == "__main__":
    unittest.main()
