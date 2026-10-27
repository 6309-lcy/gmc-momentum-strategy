"""Boundary, missing-data and calendar contracts."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import warnings

import numpy as np
import pandas as pd

from rebalancing import calendar_dates, load_config, load_evaluation, load_training, require_joint_training
from rebalancing.data_access import load_weights


class DataCutoffTests(unittest.TestCase):
    def test_dynamic_configuration_validation(self):
        config = load_config()
        for updates in [{'risk_ewma_decay':1.}, {'dynamic_risk_budget':-.1},
                        {'loss_drawdown_threshold':.1},
                        {'loss_drawdown_threshold':.1,'loss_reduction_factor':1.}]:
            changed = dict(config, **updates)
            with self.assertRaises(ValueError):
                from rebalancing.data_access import validate_config
                validate_config(changed)

    def setUp(self):
        self.config = load_config()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            self.training = load_training(self.config)

    def test_training_boundaries(self):
        self.assertEqual(str(self.training.index[0].date()), '2024-04-29')
        self.assertEqual(str(self.training.index[-1].date()), '2026-04-28')
        self.assertTrue(np.isfinite(self.training.to_numpy()).all())
        self.assertIn('provenance', self.training.attrs)

    def test_fixed_calendar_and_evaluation(self):
        dates = calendar_dates(self.config)
        self.assertEqual(len(dates), 64)
        self.assertNotIn(pd.Timestamp('2026-07-03'), dates)
        evaluation = load_evaluation(self.config)
        pd.testing.assert_index_equal(evaluation.index, dates)
        self.assertEqual(evaluation.shape, (64, 15))
        self.assertEqual(len(evaluation.pct_change(fill_method=None).iloc[1:]), 63)

    def _reject_panel(self, panel):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prices.csv'
            panel.to_csv(path)
            config = deepcopy(self.config)
            config['training_path'] = str(path)
            with self.assertRaises(ValueError):
                load_training(config)

    def test_post_cutoff_row_rejected(self):
        panel = self.training.copy()
        panel.loc[pd.Timestamp('2026-04-29')] = panel.iloc[-1]
        self._reject_panel(panel)

    def test_missing_session_rejected(self):
        self._reject_panel(self.training.drop(self.training.index[10]))

    def test_duplicate_date_rejected(self):
        self._reject_panel(pd.concat([self.training.iloc[:1], self.training]))

    def test_no_fill_or_nonpositive_prices(self):
        for value in (np.nan, np.inf, 0, -1):
            with self.subTest(value=value):
                panel = self.training.copy()
                panel.iloc[10, 0] = value
                self._reject_panel(panel)

    def test_evaluation_missing_price_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            panel = load_evaluation(self.config)
            panel.iloc[4, 2] = np.nan
            path = Path(directory) / 'eval.csv'
            panel.to_csv(path)
            config = deepcopy(self.config)
            config['evaluation_path'] = str(path)
            with self.assertRaises(ValueError):
                load_evaluation(config)

    def test_joint_bootstrap_requires_every_benchmark(self):
        weights = load_weights(self.config)
        stocks = self.training[list(weights.index)]
        with self.assertRaisesRegex(ValueError, 'Joint simulation blocked'):
            require_joint_training(stocks, weights)
        if not self.training.attrs['missing_benchmarks']:
            joint = require_joint_training(self.training, weights)
            self.assertEqual(joint.shape, (len(self.training) - 1, 15))

    def test_invalid_config(self):
        from rebalancing.data_access import validate_config
        for key, value in [('cutoff', '2026-05-02'), ('transaction_cost_bps', -1),
                           ('annual_borrow_rate', np.nan), ('risk_budget', 0),
                           ('n_paths', 0), ('training_start', '2024-4-29')]:
            with self.subTest(key=key):
                config = deepcopy(self.config)
                config[key] = value
                with self.assertRaises(ValueError):
                    validate_config(config)


if __name__ == '__main__':
    unittest.main()
