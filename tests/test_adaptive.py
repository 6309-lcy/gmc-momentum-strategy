import unittest

import numpy as np
import pandas as pd

from rebalancing.accounting import run_path
from rebalancing.adaptive import causal_covariances


class AdaptiveTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2026-01-01", periods=5)
        self.prices = pd.DataFrame({"A": [100., 100., 110., 110., 110.],
                                    "B": [100., 100., 90., 90., 90.]}, index=self.dates)
        self.weights = pd.Series({"A": .5, "B": -.5})

    def test_covariance_is_causal_and_has_entry_initialization(self):
        training = pd.DataFrame({"A": [100., 101., 99., 102.],
                                 "B": [100., 98., 101., 100.]},
                                index=pd.date_range("2025-01-01", periods=4))
        changed = self.prices.copy()
        changed.iloc[3:, 0] = [1000., 1000.]
        first = causal_covariances(training, self.prices)
        second = causal_covariances(training, changed)
        np.testing.assert_allclose(first[:3], second[:3])
        self.assertFalse(np.allclose(first[0], first[1]))
        with self.assertRaises(ValueError):
            causal_covariances(training, self.prices, decay=1.1)

    def test_loss_trigger_is_per_ledger_and_permanent(self):
        prices = pd.DataFrame({"A": [100., 100., 50., 50., 50.],
                               "B": [100., 100., 100., 100., 100.]}, index=self.dates)
        result = run_path(prices, pd.Series({"A": .9, "B": 0.}),
                          list(self.dates[1:-1]), capital=1000,
                          decision_policy={"mode": "loss", "threshold": .1,
                                           "reduction_factor": .5})
        log = result["decision_log"]
        net = log[log.ledger == "net"]
        self.assertEqual(net.target_scale.iloc[0], 1.)
        self.assertEqual(net.target_scale.iloc[1], 1.)
        self.assertEqual(net.target_scale.iloc[2], .5)
        self.assertTrue((log[log.ledger == "gross"].target_scale <= 1.).all())

    def test_risk_decision_uses_previous_close_and_fixed_fill(self):
        cov = np.zeros((len(self.dates), 2, 2))
        cov[:, 0, 0] = 4.
        base = run_path(self.prices, self.weights, [self.dates[1]], capital=1000,
                        decision_policy={"mode": "risk", "threshold": .9,
                                         "reduction_factor": .5},
                        risk_covariances=cov)
        changed = self.prices.copy()
        changed.iloc[2:, 0] = 1000.
        future = run_path(changed, self.weights, [self.dates[1]], capital=1000,
                          decision_policy={"mode": "risk", "threshold": .9,
                                           "reduction_factor": .5},
                          risk_covariances=cov)
        pd.testing.assert_frame_equal(base['orders'][base['orders'].date <= self.dates[1]].reset_index(drop=True),
                                      future['orders'][future['orders'].date <= self.dates[1]].reset_index(drop=True))
        self.assertEqual(base["decision_log"].iloc[0].target_scale, .9)

    def test_risk_diagnostics_without_triggers_and_nonpositive_drawdown(self):
        cov = np.repeat(np.eye(2)[None,:,:], len(self.dates), axis=0)
        result = run_path(self.prices, self.weights, [], capital=1000, risk_covariances=cov)
        self.assertTrue(np.isfinite(result['risk_history'].volatility).all())
        self.assertTrue((result['risk_history'].drawdown <= 0).all())
        self.assertGreater(result['risk_history'].volatility.iloc[0], 0)

    def test_loss_trigger_with_empty_schedule(self):
        prices = self.prices.copy()
        prices['A'] = [100, 100, 50, 50, 50]
        result = run_path(prices, pd.Series({'A':.9,'B':0}), [], capital=1000,
                          decision_policy={'mode':'loss','threshold':.1,'reduction_factor':.5})
        self.assertEqual(result['decision_log'].query("ledger == 'net'").target_scale.iloc[-1], .5)
        trades = result['trades'].query("kind == 'loss_reduction'")
        self.assertEqual(set(trades.date), {self.dates[3]})

    def test_ledger_reconciliation_and_terminal_suppression(self):
        result = run_path(self.prices, self.weights, list(self.dates), capital=1000,
                          decision_policy={"mode": "loss", "threshold": .1,
                                           "reduction_factor": .5})
        self.assertLess(result["orders"].date.max(), self.dates[-1])
        self.assertEqual(result['decision_log'].fill_date.max(), self.dates[-2])
        self.assertAlmostEqual(result["attribution"].net_pnl.sum(),
                               result["nav"].iloc[-1].nav - 1000)
        self.assertEqual(len(result["risk_history"]), len(self.dates))


if __name__ == "__main__":
    unittest.main()
