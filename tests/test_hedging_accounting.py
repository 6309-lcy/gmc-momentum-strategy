import unittest

import numpy as np
import pandas as pd

from hedging.accounting import run_overlay


class HedgingAccountingTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.date_range('2026-05-01', periods=6)
        self.prices = pd.DataFrame({'SGOV': 100., 'SH': 20., 'SPY': 500., 'STOCK': 40.},
                                   index=self.dates)
        self.signals = pd.DataFrame({'hedge_active': [False, True, True, False, True, False]},
                                    index=self.dates)
        self.model = {'beta': .2}

    def run_overlay(self, prices=None, signals=None, **kwargs):
        return run_overlay(self.prices if prices is None else prices,
                           self.signals if signals is None else signals, self.model, **kwargs)

    def test_cash_rejection_keeps_holdings_and_retries(self):
        prices=self.prices.copy()
        prices.loc[self.dates[2],'SH']=200.
        signals=pd.DataFrame({'hedge_active':[False,True,True,True,True,True]},index=self.dates)
        result=self.run_overlay(prices=prices,signals=signals,on_insufficient_cash='reject')
        self.assertEqual(result['rejections'].date.iloc[0],self.dates[2])
        self.assertEqual(result['nav'].sh_value.iloc[2],0)
        self.assertGreater(result['nav'].sh_value.iloc[3],0)
        self.assertTrue((result['nav'].cash>=0).all())

    def test_initial_reserve_and_default_capitals(self):
        result = self.run_overlay()
        row = result['nav'].iloc[0]
        self.assertEqual(row.sgov_value, 196e6)
        self.assertEqual(row.sh_value, 0)
        self.assertEqual(row.transaction_cost, 196000)
        self.assertEqual(row.cash, 3804000)
        self.assertEqual(row.nav, 199804000)
        self.assertEqual(row.liquidation_nav, 199608000)
        self.assertEqual(set(result), {'nav', 'trades', 'orders', 'daily_positions',
                                       'costs', 'terminal_notional', 'rejections'})

    def test_modes_and_beta_aliases(self):
        for key in ('beta', 'beta_clipped', 'hedge_beta'):
            for mode in ('reserve', 'static', 'dynamic'):
                with self.subTest(key=key, mode=mode):
                    result = run_overlay(self.prices, self.signals, {key: 1.}, mode=mode)
                    nav = result['nav']
                    if mode == 'reserve':
                        self.assertTrue((nav.sh_value == 0).all())
                        self.assertFalse(nav.signal_active.any())
                    elif mode == 'static':
                        self.assertEqual(nav.iloc[0].target_sh, 196e6)
                        self.assertEqual(nav.iloc[0].sgov_value, 0)
                        self.assertTrue(nav.signal_active.all())
                    else:
                        self.assertEqual(nav.signal_active.tolist(),
                                         [False, False, True, True, False, False])

    def test_initial_active_uses_first_signal(self):
        signals = self.signals.copy()
        signals.iloc[0, 0] = True
        nav = self.run_overlay(signals=signals)['nav']
        self.assertEqual(nav.iloc[0].sh_value, 100e6)
        self.assertEqual(nav.iloc[0].sgov_value, 96e6)

    def test_constant_prices_only_lose_actual_fees(self):
        result = self.run_overlay()
        nav, trades = result['nav'], result['trades']
        actual = trades[~trades.hypothetical]
        np.testing.assert_allclose(nav.nav, 200e6 - nav.transaction_cost.cumsum())
        np.testing.assert_allclose(nav.nav, nav.cash + nav.sgov_value + nav.sh_value)
        np.testing.assert_allclose(nav.liquidation_nav,
                                   nav.nav - .001 * (nav.sgov_value + nav.sh_value))
        self.assertAlmostEqual(actual.transaction_cost.sum(), nav.transaction_cost.sum())
        self.assertAlmostEqual(result['costs'].query('not hypothetical').amount.sum(),
                               nav.transaction_cost.sum())
        self.assertAlmostEqual(trades[trades.hypothetical].transaction_cost.sum(),
                               nav.iloc[-1].liquidation_cost)
        self.assertAlmostEqual(result['terminal_notional'],
                               nav.iloc[-1].sgov_value + nav.iloc[-1].sh_value)
        self.assertEqual(set(actual.ticker), {'SGOV', 'SH'})
        self.assertTrue((nav.cash >= 0).all())

    def test_daily_cash_and_price_pnl_reconcile(self):
        prices = self.prices.copy()
        prices['SGOV'] = [100., 100.01, 100.02, 100.03, 100.04, 100.05]
        prices['SH'] = [20., 20.1, 20.11, 20.12, 20.13, 20.14]
        result = self.run_overlay(prices=prices)
        nav = result['nav']
        actual = result['trades'].query('not hypothetical')
        cash_flow = (actual.notional + actual.transaction_cost).groupby(actual.date).sum()
        np.testing.assert_allclose(nav.cash, 200e6 - cash_flow.reindex(self.dates, fill_value=0).cumsum())
        price_pnl = (nav.sgov_quantity.shift() * prices.SGOV.diff()
                     + nav.sh_quantity.shift() * prices.SH.diff()).fillna(0)
        np.testing.assert_allclose(nav.nav, 200e6 + price_pnl.cumsum() - nav.transaction_cost.cumsum())
        self.assertEqual(len(result['daily_positions']), 2 * len(prices))

    def test_orders_fixed_before_future_fill(self):
        baseline = self.run_overlay()
        changed = self.prices.copy()
        changed.loc[self.dates[2], 'SH'] = 20.01
        altered = self.run_overlay(prices=changed)
        original_orders = baseline['orders'].query('date == @self.dates[2]')
        altered_orders = altered['orders'].query('date == @self.dates[2]')
        pd.testing.assert_frame_equal(original_orders, altered_orders)
        pd.testing.assert_frame_equal(baseline['nav'].iloc[:2], altered['nav'].iloc[:2])
        original_trades = baseline['trades'].query('date == @self.dates[2]')
        altered_trades = altered['trades'].query('date == @self.dates[2]')
        np.testing.assert_array_equal(original_trades.quantity, altered_trades.quantity)
        self.assertNotEqual(original_trades.notional.sum(), altered_trades.notional.sum())
        prior_nav = baseline['nav'].iloc[1].nav
        self.assertAlmostEqual(original_orders.target_notional.sum(), .98 * prior_nav)
        self.assertAlmostEqual(original_orders.reference_nav.iloc[0], prior_nav)

    def test_only_initial_and_signal_changes_trade_and_final_suppressed(self):
        result = self.run_overlay()
        actual = result['trades'].query('not hypothetical')
        self.assertEqual(set(actual.date), set(self.dates[[0, 2, 4]]))
        self.assertEqual(result['nav'].iloc[-1].transaction_cost, 0)
        self.assertEqual(result['nav'].iloc[-1].sh_quantity, result['nav'].iloc[-2].sh_quantity)
        self.assertFalse(result['nav'].iloc[-1].signal_active)
        self.assertTrue((result['trades'].query('hypothetical').date == self.dates[-1]).all())

    def test_gap_and_fee_exhaustion_raise(self):
        prices = self.prices.copy()
        prices.loc[self.dates[2], 'SH'] = 40.
        with self.assertRaisesRegex(ValueError, 'exhaust buffer'):
            self.run_overlay(prices=prices)
        with self.assertRaisesRegex(ValueError, 'exhaust buffer'):
            self.run_overlay(cash_buffer=0)
        with self.assertRaisesRegex(ValueError, 'exhaust buffer'):
            self.run_overlay(trading_cost=.1)

    def test_fractional_units_and_single_observation(self):
        result = self.run_overlay(prices=self.prices.iloc[:1], signals=self.signals.iloc[:1],
                                  capital=1001, trading_cost=0)
        self.assertAlmostEqual(result['nav'].iloc[0].sgov_quantity, 9.8098)
        self.assertAlmostEqual(result['nav'].iloc[0].nav, 1001)
        self.assertEqual(len(result['orders']), 1)

    def test_inputs_untouched_and_optional_stocks_do_not_affect_overlay(self):
        prices, signals, model = self.prices.copy(), self.signals.copy(), self.model.copy()
        baseline = self.run_overlay()
        pd.testing.assert_frame_equal(self.prices, prices)
        pd.testing.assert_frame_equal(self.signals, signals)
        self.assertEqual(self.model, model)
        prices['STOCK'] *= 100
        prices['SPY'] *= 2
        pd.testing.assert_frame_equal(baseline['nav'], self.run_overlay(prices=prices)['nav'])
        pd.testing.assert_frame_equal(baseline['nav'],
                                      self.run_overlay(prices=prices.drop(columns='STOCK'))['nav'])

    def test_strict_price_and_signal_validation(self):
        for column in self.prices:
            for value in (np.nan, np.inf, -1., 0.):
                with self.subTest(column=column, value=value):
                    prices = self.prices.copy()
                    prices.loc[self.dates[2], column] = value
                    with self.assertRaises(ValueError):
                        self.run_overlay(prices=prices)
        for prices in (self.prices.iloc[::-1], self.prices.iloc[0:0],
                       self.prices.drop(columns='SPY')):
            with self.assertRaises(ValueError):
                self.run_overlay(prices=prices)
        for signals in (self.signals.iloc[::-1], self.signals.iloc[1:],
                        self.signals.rename(columns={'hedge_active': 'active'})):
            with self.assertRaises(ValueError):
                self.run_overlay(signals=signals)
        for state in (None, 'False', 2):
            signals = self.signals.astype(object)
            signals.iloc[2, 0] = state
            with self.assertRaises(ValueError):
                self.run_overlay(signals=signals)

    def test_parameter_validation(self):
        for kwargs in ({'capital': 0}, {'stock_capital': -1}, {'cash_buffer': 1},
                       {'cash_buffer': -.1}, {'trading_cost': -1}, {'capital': np.inf},
                       {'mode': 'unknown'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_overlay(**kwargs)
        for model in ({}, {'beta': np.nan}, {'beta': -1}, {'beta': 2}, {'beta': 'x'}):
            with self.subTest(model=model), self.assertRaises(ValueError):
                run_overlay(self.prices, self.signals, model)


if __name__ == '__main__':
    unittest.main()
