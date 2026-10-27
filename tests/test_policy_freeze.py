"""Training-only freeze, detached snapshots and risk accounting."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import warnings

import numpy as np
import pandas as pd

from rebalancing import diagnostics, freeze_policy, load_config, load_training, verify_freeze


class PolicyFreezeTests(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            self.training = load_training(self.config)

    def test_freeze_never_opens_evaluation(self):
        self.config['evaluation_path'] = 'does-not-exist.csv'
        with patch('rebalancing.data_access.load_evaluation', side_effect=AssertionError('evaluation access')):
            frozen = freeze_policy(self.config, self.training)
        self.assertIsNone(frozen['k'])
        self.assertIsNone(frozen['risk_weights'])
        self.assertEqual(frozen['risk_policy_status'], 'unconfigured')
        self.assertEqual(len(frozen['session_dates']), 64)
        self.assertEqual(frozen['rebalance_dates'], ['2026-06-01', '2026-07-01'])
        self.assertNotIn('2026-08-03', frozen['rebalance_dates'])
        self.assertTrue(verify_freeze(frozen))

    def test_input_objects_unchanged_and_detached(self):
        config_before = deepcopy(self.config)
        training_before = self.training.copy(deep=True)
        frozen = freeze_policy(self.config, self.training)
        self.assertEqual(self.config, config_before)
        pd.testing.assert_frame_equal(self.training, training_before)
        self.config['benchmark_weights']['URTH'] = .1
        self.training.iloc[5, 0] *= 2
        self.assertEqual(frozen['config'], config_before)
        self.assertTrue(verify_freeze(frozen))

    def test_deterministic_and_tamper_evident(self):
        first = freeze_policy(self.config, self.training)
        second = freeze_policy(self.config, self.training)
        self.assertEqual(first, second)
        first['weights']['WDC'] += .01
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            verify_freeze(first)

    def test_training_hash_changes_with_observations(self):
        first = freeze_policy(self.config, self.training)
        self.training.iloc[50, 0] *= 1.001
        second = freeze_policy(self.config, self.training)
        self.assertNotEqual(first['training_hash'], second['training_hash'])
        self.assertNotEqual(first['freeze_hash'], second['freeze_hash'])

    def test_future_training_rejected_at_freeze(self):
        self.training.loc[pd.Timestamp('2026-04-29')] = self.training.iloc[-1]
        with self.assertRaises(ValueError):
            freeze_policy(self.config, self.training)

    def test_risk_budget_scales_exposures(self):
        self.config['risk_budget'] = .01
        frozen = freeze_policy(self.config, self.training)
        self.assertGreater(frozen['k'], 0)
        self.assertLess(frozen['k'], 1)
        for ticker, weight in frozen['weights'].items():
            self.assertAlmostEqual(frozen['risk_weights'][ticker], weight * frozen['k'])
        risk = diagnostics(self.training, frozen['risk_weights'], frozen['sectors']).set_index('metric')['value']
        self.assertAlmostEqual(risk['lw_volatility'], .01)

    def test_risk_contributions_and_missing_benchmarks(self):
        frozen = freeze_policy(self.config, self.training)
        stocks = self.training[list(frozen['weights'])]
        risk = diagnostics(stocks, frozen['weights'], frozen['sectors']).set_index('metric')['value']
        self.assertAlmostEqual(risk['gross_exposure'], 1)
        self.assertAlmostEqual(risk['net_exposure'], .6)
        contributions = risk[risk.index.str.startswith('risk_contribution:')]
        self.assertAlmostEqual(contributions.sum(), risk['lw_volatility'])
        self.assertTrue(np.isnan(risk['beta:URTH']))
        self.assertTrue(np.isnan(risk['tracking_error:FundX']))
        self.assertTrue(np.isfinite(risk['stress_worst_63_session_return']))


if __name__ == '__main__':
    unittest.main()
