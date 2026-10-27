import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from rebalancing.path_plots import _asset_paths, _portfolio_figure, write_path_plots
from rebalancing.simulation import joint_indices


class PathPlotTests(unittest.TestCase):
    def setUp(self):
        self.training = pd.DataFrame(
            {'AAA': [100., 102., 99., 103., 104., 101.],
             'BBB': [50., 49., 51., 52., 50., 53.],
             'URTH': [90., 91., 89., 92., 93., 94.]},
            index=pd.bdate_range('2026-04-20', periods=6))
        self.policy = {'weights': {'AAA': .8, 'BBB': -.2}, 'n_paths': 7,
                       'block_length': 2, 'seed': 42, 'cutoff': '2026-04-27',
                       'session_dates': ['2026-05-01', '2026-05-04',
                                         '2026-05-05', '2026-05-06']}

    def test_joint_prices_and_stock_only_lw_ewma(self):
        decay = .81
        frame, prices, volatility = _asset_paths(
            self.training, self.policy, {'risk_ewma_decay': decay, 'seed': 999})
        returns = self.training.pct_change().iloc[1:]
        indices = joint_indices(len(returns), 3, 7, 2, 42)
        sampled = returns[['AAA', 'BBB']].to_numpy()[indices]
        expected_prices = np.concatenate([np.ones((7, 1, 2)),
                                           np.cumprod(1 + sampled, axis=1)], axis=1)
        expected_prices *= self.training.iloc[-1][['AAA', 'BBB']].to_numpy()
        np.testing.assert_allclose(prices, expected_prices[:5])
        initial = np.diag(LedoitWolf().fit(returns[['AAA', 'BBB']]).covariance_) * 252
        expected_variance = np.empty((7, 4, 2))
        expected_variance[:, 0] = initial
        for time in range(1, 4):
            expected_variance[:, time] = (decay * expected_variance[:, time - 1] +
                                          (1 - decay) * sampled[:, time - 1] ** 2 * 252)
        expected_volatility = np.sqrt(expected_variance)
        np.testing.assert_allclose(volatility, expected_volatility[:5])
        for metric, values in [('price', expected_prices), ('volatility', expected_volatility)]:
            quantiles = np.quantile(values, [.05, .5, .95], axis=0)
            for i, q in enumerate(('q05', 'q50', 'q95')):
                np.testing.assert_allclose(frame[f'{metric}_{q}'], quantiles[i].reshape(-1))
        repeat = _asset_paths(self.training, self.policy, {'risk_ewma_decay': decay})
        pd.testing.assert_frame_equal(frame, repeat[0])
        np.testing.assert_array_equal(prices, repeat[1])
        self.assertEqual(frame.ticker.tolist(), ['AAA', 'BBB'] * 4)
        self.assertEqual(frame.date.iloc[-1], pd.Timestamp('2026-05-06'))

    def test_default_decay_and_post_cutoff_rejection(self):
        default = _asset_paths(self.training, self.policy, {})
        explicit = _asset_paths(self.training, self.policy, {'risk_ewma_decay': .94})
        pd.testing.assert_frame_equal(default[0], explicit[0])
        with self.assertRaisesRegex(ValueError, 'post-cutoff'):
            _asset_paths(self.training, dict(self.policy, cutoff='2026-04-24'), {})
        with self.assertRaisesRegex(ValueError, 'risk_ewma_decay'):
            _asset_paths(self.training, self.policy, {'risk_ewma_decay': 1.1})

    def test_saved_portfolio_summaries_and_first_five_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            rows, examples = [], []
            for strategy in ('P0', 'P1', 'P4', 'P5'):
                for metric in ('nav', 'volatility', 'drawdown'):
                    for date in self.policy['session_dates']:
                        rows.append(dict(date=date, strategy=strategy, metric=metric,
                                         q05=1., q50=2., q95=3.))
                        for path in range(7):
                            examples.append(dict(path=path, date=date, strategy=strategy,
                                                 metric=metric, value=path + 10.))
            pd.DataFrame(rows).to_csv(out / 'simulation_path_quantiles.csv', index=False)
            pd.DataFrame(examples).to_csv(out / 'simulation_path_examples.csv', index=False)
            with patch('rebalancing.path_plots._save') as save:
                _portfolio_figure(out)
                fig = save.call_args.args[0]
                try:
                    for ax in fig.axes:
                        self.assertEqual(len(ax.collections), 4)
                        self.assertEqual(len(ax.lines), 24)
                        self.assertEqual([line.get_label() for line in ax.lines[::6]],
                                         ['P0: buy and hold', 'P1: monthly', 'P4: daily', 'P5: weekly'])
                        np.testing.assert_allclose(ax.lines[0].get_ydata(), 2.)
                        for line, expected in zip(ax.lines[1:6], range(10, 15)):
                            np.testing.assert_allclose(line.get_ydata(), expected)
                finally:
                    plt.close(fig)

    def test_outputs_without_portfolio_summaries(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with patch('rebalancing.simulation.run_path', side_effect=AssertionError('Accounting rerun')):
                frame = write_path_plots(self.training, self.policy, {}, out)
            saved = pd.read_csv(out / 'asset_path_quantiles.csv', parse_dates=['date'])
            pd.testing.assert_frame_equal(saved, frame)
            for stem in ('asset_price_simulation', 'asset_risk_simulation', 'portfolio_simulation'):
                svg = (out / 'figures' / f'{stem}.svg').read_text(encoding='utf-8')
                self.assertIn('<text', svg)
                self.assertIn('Quantile curves are not individual paths.', svg)
                self.assertIn('first five deterministic', svg)
                self.assertTrue(all(line == line.rstrip() for line in svg.splitlines()))
                self.assertTrue((out / 'figures' / f'{stem}.png').read_bytes().startswith(b'\x89PNG'))
            self.assertIn('Saved quantiles unavailable: P0, P1, P4, P5', svg)
            self.assertFalse(plt.get_fignums())


if __name__ == '__main__':
    unittest.main()
