import unittest

import numpy as np
import pandas as pd

from rebalancing.accounting import run_path
from rebalancing.execution import round_orders


class ExecutionTimingTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range("2026-01-28", periods=4)
        self.prices = pd.DataFrame({"A": [10., 20., 30., 40.]}, index=self.dates)
        self.weights = pd.Series({"A": .5})

    def test_order_uses_preceding_close_and_fills_fixed_quantity(self):
        result = run_path(self.prices, self.weights, [self.dates[2]], capital=1000,
                          trading_cost=0, borrow_rate=0)
        order = result["orders"].query("kind == 'rebalance'").iloc[0]
        trade = result["trades"].query("kind == 'rebalance'").iloc[0]
        self.assertEqual(order.signal_date, self.dates[1])
        self.assertEqual(order.date, self.dates[2])
        self.assertEqual(order.reference_nav, 1500)
        self.assertEqual(order.reference_price, 20)
        self.assertEqual(order.quantity, -12)  # Round -12.5 to even.
        self.assertEqual(trade.quantity, order.quantity)
        self.assertEqual(trade.price, 30)
        self.assertEqual(result["nav"].iloc[2].nav, 2000)
        self.assertEqual(result["nav"].iloc[3].nav, 2380)

    def test_fill_price_and_future_prices_cannot_change_order(self):
        changed = self.prices.copy()
        changed.iloc[2:, 0] = [35., 50.]
        args = dict(weights=self.weights, rebalance_dates=[self.dates[2]], capital=1000,
                    trading_cost=0, borrow_rate=0)
        original = run_path(self.prices, **args)
        alternate = run_path(changed, **args)
        pd.testing.assert_frame_equal(original["orders"], alternate["orders"])
        self.assertNotEqual(original["trades"].iloc[1].price, alternate["trades"].iloc[1].price)

    def test_terminal_date_never_rebalances(self):
        plain = run_path(self.prices, self.weights, [], capital=1000)
        scheduled = run_path(self.prices, self.weights, [self.dates[-1]], capital=1000)
        for name in plain:
            if isinstance(plain[name], pd.DataFrame):
                pd.testing.assert_frame_equal(plain[name], scheduled[name])
            else:
                self.assertEqual(plain[name], scheduled[name])

    def test_initial_fractional_units_and_duplicate_dates(self):
        prices = pd.DataFrame({"A": [3., 4., 5., 6.]}, index=self.dates)
        result = run_path(prices, self.weights,
                          [self.dates[0], self.dates[2], self.dates[2]], capital=1000)
        entry = result["trades"].iloc[0]
        self.assertAlmostEqual(entry.quantity, 500 / 3)
        self.assertEqual(entry.kind, "initial_close_diagnostic")
        self.assertEqual(entry.signal_date, self.dates[0])
        self.assertEqual(len(result["orders"].query("kind == 'rebalance'")), 1)

    def test_round_orders_aligns_labels_and_rounds_trade_delta(self):
        weights = pd.Series({"A": .5, "B": -.2})
        prices = pd.Series({"B": 20., "A": 10.})
        quantities = pd.Series({"B": -9.6, "A": 49.2})
        orders = round_orders(weights, 1000, prices, quantities)
        pd.testing.assert_series_equal(orders, pd.Series({"A": 1., "B": 0.}, name="quantity"))
        self.assertTrue(np.equal(orders, np.rint(orders)).all())

    def test_round_orders_validation(self):
        for prices, quantities, nav in [([0.], [0.], 1000), ([np.nan], [0.], 1000),
                                         ([10.], [np.inf], 1000), ([10.], [0.], 0),
                                         (pd.Series({"B": 10.}), [0.], 1000)]:
            with self.subTest(prices=prices, quantities=quantities, nav=nav):
                with self.assertRaises(ValueError):
                    round_orders(self.weights, nav, prices, quantities)

    def test_engine_and_public_sizing_agree(self):
        result = run_path(self.prices, self.weights, [self.dates[2]], capital=1000)
        entry = result["trades"].iloc[0].quantity
        expected = round_orders(self.weights, result["nav"].iloc[1].nav,
                                self.prices.iloc[1], pd.Series({"A": entry}))
        actual = result["orders"].query("kind == 'rebalance'").iloc[0].quantity
        self.assertEqual(actual, expected.iloc[0])


if __name__ == "__main__":
    unittest.main()
