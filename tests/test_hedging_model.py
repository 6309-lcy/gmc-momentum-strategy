"""Frozen hedging estimates, hysteresis and evaluation causality."""
from copy import deepcopy
import json
import unittest

import numpy as np
import pandas as pd

from hedging.model import fit_model, filter_states


def price_panel(returns, start):
    values = np.vstack([np.ones(returns.shape[1]), np.cumprod(1 + returns, axis=0)]) * 100
    return pd.DataFrame(values, columns=['A', 'B', 'SPY'],
                        index=pd.bdate_range(start, periods=len(values)))


class HedgingModelTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(27)
        self.training = price_panel(rng.normal(0, .014, (100, 3)), '2025-11-03')
        self.weights = pd.Series({'A': .7, 'B': -.2})
        self.prices = price_panel(rng.normal(0, .02, (40, 3)), '2026-04-29')
        self.model = fit_model(self.training, self.weights)

    def test_empirical_seed_ewma_thresholds_and_beta(self):
        returns = self.training.pct_change(fill_method=None).iloc[1:]
        portfolio = returns[['A', 'B']] @ self.weights
        variance = np.mean(portfolio.iloc[:21].to_numpy() ** 2)
        volatility = []
        for value in portfolio.iloc[21:]:
            variance = .94 * variance + .06 * value ** 2
            volatility.append(np.sqrt(252 * variance))
        self.assertAlmostEqual(self.model['initial_variance'], variance)
        self.assertAlmostEqual(self.model['entry_threshold'], np.quantile(volatility, .75))
        self.assertAlmostEqual(self.model['exit_threshold'], np.quantile(volatility, .50))
        beta = portfolio.cov(returns['SPY']) / returns['SPY'].var()
        self.assertAlmostEqual(self.model['beta_raw'], beta)
        self.assertAlmostEqual(self.model['beta'], np.clip(beta, 0, 1))
        np.testing.assert_allclose(self.model['trailing_spy_returns'], returns['SPY'].iloc[-21:])

    def test_training_state_scans_hysteresis(self):
        returns = self.training.pct_change(fill_method=None).iloc[1:]
        portfolio = returns[['A', 'B']] @ self.weights
        variance = np.mean(portfolio.iloc[:21].to_numpy() ** 2)
        state = 'normal'
        for i in range(20, len(returns)):
            if i > 20:
                variance = .94 * variance + .06 * portfolio.iloc[i] ** 2
            vol = np.sqrt(252 * variance)
            trend = (1 + returns['SPY'].iloc[i - 20:i + 1]).prod() - 1
            if state == 'normal':
                if vol > self.model['entry_threshold'] and trend < 0:
                    state = 'stress'
            elif vol < self.model['exit_threshold'] or trend >= 0:
                state = 'normal'
        self.assertEqual(self.model['initial_state'], state)

    def test_observation_zero_and_first_completed_return(self):
        result = filter_states(self.prices, self.model, self.weights)
        first = result.iloc[0]
        self.assertAlmostEqual(first['volatility'], np.sqrt(252 * self.model['initial_variance']))
        self.assertAlmostEqual(first['trend_21'], np.prod(1 + np.array(self.model['trailing_spy_returns'])) - 1)
        self.assertEqual(first['state'], self.model['initial_state'])
        portfolio_return = (self.prices.iloc[1][self.weights.index] /
                            self.prices.iloc[0][self.weights.index] - 1) @ self.weights
        variance = .94 * self.model['initial_variance'] + .06 * portfolio_return ** 2
        self.assertAlmostEqual(result.iloc[1]['volatility'], np.sqrt(252 * variance))
        trailing = self.model['trailing_spy_returns'][1:] + [self.prices['SPY'].iloc[1] / self.prices['SPY'].iloc[0] - 1]
        self.assertAlmostEqual(result.iloc[1]['trend_21'], np.prod(1 + np.array(trailing)) - 1)
        pd.testing.assert_series_equal(result['hedge_active'], (result['state'] == 'stress').rename('hedge_active'))
        scaled = self.prices * pd.Series({'A': 3., 'B': .5, 'SPY': 8.})
        pd.testing.assert_frame_equal(result, filter_states(scaled, self.model, self.weights), atol=1e-12)

    def test_prefix_equality_and_future_perturbation(self):
        result = filter_states(self.prices, self.model, self.weights)
        for length in (1, 2, 15, 22, len(self.prices)):
            pd.testing.assert_frame_equal(result.iloc[:length],
                                          filter_states(self.prices.iloc[:length], self.model, self.weights))
        changed = self.prices.copy(deep=True)
        changed.iloc[20:] *= np.linspace(.4, 3, len(changed) - 20)[:, None]
        perturbed = filter_states(changed, self.model, self.weights)
        pd.testing.assert_frame_equal(result.iloc[:20], perturbed.iloc[:20])
        self.assertFalse(result.iloc[20:].equals(perturbed.iloc[20:]))

    def test_freeze_json_determinism_and_no_mutation(self):
        training_before = self.training.copy(deep=True)
        weights_before = self.weights.copy(deep=True)
        prices_before = self.prices.copy(deep=True)
        model = fit_model(self.training, self.weights)
        before = deepcopy(model)
        restored = json.loads(json.dumps(model, allow_nan=False))
        self.assertEqual(model, restored)
        self.assertEqual(model, fit_model(self.training, self.weights))
        filter_states(self.prices, restored, self.weights)
        pd.testing.assert_frame_equal(self.training, training_before)
        pd.testing.assert_series_equal(self.weights, weights_before)
        pd.testing.assert_frame_equal(self.prices, prices_before)
        self.assertEqual(model, before)
        self.assertEqual(restored, before)
        self.training.iloc[30, 0] *= 1.1
        self.assertEqual(model, before)
        self.assertNotEqual(fit_model(self.training, self.weights)['training_hash'], model['training_hash'])
        self.assertNotEqual(fit_model(self.training, self.weights)['freeze_hash'], model['freeze_hash'])

    def test_tampering_and_new_weights_rejected(self):
        for key, value in [('entry_threshold', 100.), ('initial_variance', .1), ('initial_state', 'other')]:
            changed = deepcopy(self.model)
            changed[key] = value
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                filter_states(self.prices, changed, self.weights)
        changed = deepcopy(self.model)
        changed['config']['decay'] = .5
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            filter_states(self.prices, changed, self.weights)
        with self.assertRaisesRegex(ValueError, 'weights'):
            filter_states(self.prices, self.model, self.weights * .5)

    def test_cutoff_and_invalid_inputs(self):
        training = self.training.copy()
        training.index = pd.bdate_range(end='2026-04-28', periods=len(training))
        fit_model(training, self.weights)
        training.loc[pd.Timestamp('2026-04-29')] = training.iloc[-1]
        with self.assertRaisesRegex(ValueError, '2026-04-28'):
            fit_model(training, self.weights)
        for decay in (0, 1, -1, np.nan):
            with self.assertRaises(ValueError):
                fit_model(self.training, self.weights, decay)
        with self.assertRaises(ValueError):
            fit_model(self.training.iloc[:22], self.weights)
        for bad in (self.training.iloc[::-1], self.training.drop(columns='SPY'),
                    self.training.mask(self.training == self.training.iloc[5, 0])):
            with self.assertRaises(ValueError):
                fit_model(bad, self.weights)

    def test_beta_clipping(self):
        market = np.tile([-.01, .02, -.03, .01], 15)
        for coefficient, clipped in [(2., 1.), (-.5, 0.)]:
            panel = price_panel(np.column_stack([coefficient * market, market, market]), '2025-11-03')
            model = fit_model(panel, pd.Series({'A': 1.}))
            self.assertAlmostEqual(model['beta_raw'], coefficient)
            self.assertEqual(model['beta'], clipped)

    def test_evaluation_hysteresis_boundaries(self):
        market = np.tile([-.005, -.006], 40)
        panel = price_panel(np.column_stack([market, market, market]), '2025-11-03')
        model = fit_model(panel, pd.Series({'A': 1.}))
        evaluation = price_panel(np.array([[-.10, 0, -.01], [0, 0, -.01], [0, 0, .50]]), '2026-04-29')
        result = filter_states(evaluation, model, pd.Series({'A': 1.}))
        self.assertEqual(result.iloc[1]['state'], 'stress')
        self.assertGreater(result.iloc[2]['volatility'], model['exit_threshold'])
        self.assertEqual(result.iloc[2]['state'], 'stress')
        self.assertGreaterEqual(result.iloc[3]['trend_21'], 0)
        self.assertEqual(result.iloc[3]['state'], 'normal')
        quiet = price_panel(np.zeros((160, 3)), '2026-04-29')
        quiet['SPY'] = 100 * .999 ** np.arange(len(quiet))
        quiet_result = filter_states(quiet, model, pd.Series({'A': 1.}))
        self.assertLess(quiet_result.iloc[-1]['volatility'], model['exit_threshold'])
        self.assertLess(quiet_result.iloc[-1]['trend_21'], 0)
        self.assertEqual(quiet_result.iloc[-1]['state'], 'normal')


if __name__ == '__main__':
    unittest.main()
