import unittest

import numpy as np
import pandas as pd

from rebalancing.accounting import run_path


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
        self.prices = pd.DataFrame({"L": [10., 11., 12.], "S": [20., 22., 18.]}, index=self.dates)
        self.weights = pd.Series({"L": .6, "S": -.2})

    def test_entry_cash_collateral_and_calendar_borrow(self):
        result = run_path(self.prices, self.weights, [], capital=1000)
        nav = result["nav"]
        self.assertAlmostEqual(nav.iloc[0].nav, 999.2)
        self.assertAlmostEqual(nav.iloc[0].cash, 599.2)
        self.assertAlmostEqual(nav.iloc[0].restricted_cash, 200)
        self.assertAlmostEqual(nav.iloc[0].available_cash, 399.2)
        self.assertAlmostEqual(nav.iloc[1].borrow_cost, 200 * .02 * 3 / 365)
        self.assertAlmostEqual(nav.iloc[2].borrow_cost, 220 * .02 / 365)
        self.assertAlmostEqual(nav.iloc[-1].gross_nav, 1140)
        self.assertAlmostEqual(nav.iloc[-1].nav, 1140 - .8 - (200 * 3 + 220) * .02 / 365)
        self.assertAlmostEqual(nav.iloc[-1].liquidation_nav, nav.iloc[-1].nav - .9)
        self.assertAlmostEqual(nav.iloc[0].turnover, .8)
        self.assertTrue((nav.restricted_cash == nav.short_market_value).all())

    def test_attribution_and_costs_reconcile_with_rebalances(self):
        result = run_path(self.prices, self.weights, [self.dates[1]], capital=1000)
        nav, attribution = result["nav"], result["attribution"]
        self.assertAlmostEqual(attribution.net_pnl.sum(), nav.iloc[-1].nav - 1000)
        self.assertAlmostEqual(attribution.gross_stock_pnl.sum(), nav.iloc[-1].gross_nav - 1000)
        self.assertAlmostEqual(attribution.liquidation_pnl.sum(), nav.iloc[-1].liquidation_nav - 1000)
        costs = result["costs"]
        actual = costs[~costs.hypothetical]
        self.assertAlmostEqual(actual.amount.sum(), nav.transaction_cost.sum() + nav.borrow_cost.sum())
        self.assertAlmostEqual(costs[costs.hypothetical].amount.sum(), attribution.liquidation_cost.sum())
        trades = result["trades"]
        self.assertEqual(set(trades[trades.hypothetical].kind), {"liquidation"})
        self.assertAlmostEqual(trades[~trades.hypothetical].transaction_cost.sum(), nav.transaction_cost.sum())

    def test_gross_matches_independent_zero_cost_run(self):
        dates = pd.date_range("2026-01-01", periods=8)
        prices = pd.DataFrame({"L": [10, 11, 9, 13, 10, 14, 11, 12],
                               "S": [20, 19, 22, 18, 21, 17, 23, 18]}, index=dates)
        rebalance = list(dates[1:-1])
        net = run_path(prices, self.weights, rebalance, capital=1000, trading_cost=.02)
        gross = run_path(prices, self.weights, rebalance, capital=1000,
                         trading_cost=0, borrow_rate=0)
        np.testing.assert_allclose(net["nav"].gross_nav, gross["nav"].nav)
        self.assertFalse(np.allclose(net["attribution"].stock_pnl, net["attribution"].gross_stock_pnl))

    def test_record_false_preserves_results(self):
        full = run_path(self.prices, self.weights, [self.dates[1]], capital=1000)
        light = run_path(self.prices, self.weights, [self.dates[1]], capital=1000, record=False)
        pd.testing.assert_frame_equal(full["nav"], light["nav"])
        pd.testing.assert_frame_equal(full["attribution"], light["attribution"])
        for name in ("orders", "trades", "costs"):
            self.assertTrue(light[name].empty)
            self.assertEqual(list(full[name].columns), list(light[name].columns))

    def test_constant_prices_do_not_create_profits_or_rebalance_costs(self):
        prices = self.prices * 0 + pd.Series({'L':10., 'S':20.})
        result = run_path(prices, self.weights, [self.dates[1]], capital=1000,
                          trading_cost=0, borrow_rate=0)
        np.testing.assert_allclose(result['nav'].nav,1000)
        self.assertEqual(result['nav'].transaction_cost.sum(),0)
        fees = run_path(prices, self.weights, [self.dates[1]], capital=1000,
                        trading_cost=.001, borrow_rate=0)
        self.assertEqual(fees['nav'].transaction_cost.iloc[1],0)
        positions = result['daily_positions'].groupby('date').market_value.sum()
        np.testing.assert_allclose(positions.values+result['nav'].cash.values,result['nav'].nav.values)

    def test_bad_prices_are_rejected(self):
        for value in (0, -1, np.nan, np.inf):
            with self.subTest(value=value):
                prices = self.prices.copy()
                prices.iloc[1, 0] = value
                with self.assertRaisesRegex(ValueError, "positive and finite"):
                    run_path(prices, self.weights, [])

    def test_invalid_inputs_are_rejected(self):
        cases = [
            (self.prices.iloc[::-1], self.weights, []),
            (self.prices, pd.Series({"X": .5}), []),
            (self.prices, self.weights, [pd.Timestamp("2026-01-03")]),
            (self.prices, pd.Series({"L": np.nan, "S": -.2}), []),
        ]
        for prices, weights, rebalance in cases:
            with self.subTest(weights=weights.to_dict(), rebalance=rebalance):
                with self.assertRaises(ValueError):
                    run_path(prices, weights, rebalance)
        for kwargs in ({"capital": 0}, {"trading_cost": -1}, {"borrow_rate": np.inf}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_path(self.prices, self.weights, [], **kwargs)

    def test_fees_cannot_be_financed(self):
        with self.assertRaisesRegex(ValueError, "available cash"):
            run_path(self.prices[["L"]], pd.Series({"L": 1.}), [], capital=1000)

    def test_collateral_failure_and_nonpositive_nav(self):
        prices = pd.DataFrame({"L": [10., 10.], "S": [10., 40.]}, index=self.dates[:2])
        with self.assertRaisesRegex(ValueError, "available cash"):
            run_path(prices, pd.Series({"L": .6, "S": -.3}), [], capital=1000)
        prices.loc[self.dates[1], "S"] = 100
        with self.assertRaisesRegex(ValueError, "NAV"):
            run_path(prices, pd.Series({"L": .6, "S": -.3}), [], capital=1000)

    def test_single_close_initial_fees_and_hypothetical_exit(self):
        result = run_path(self.prices.iloc[:1], self.weights, [self.dates[0]], capital=1000)
        self.assertAlmostEqual(result["nav"].iloc[0].nav, 999.2)
        self.assertAlmostEqual(result["nav"].iloc[0].liquidation_nav, 998.4)
        self.assertAlmostEqual(result["attribution"].net_pnl.sum(), -.8)
        self.assertEqual(set(result["orders"].kind), {"initial_close_diagnostic"})


if __name__ == "__main__":
    unittest.main()
