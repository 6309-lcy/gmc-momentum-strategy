import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from rebalancing.accounting import run_path
from rebalancing.simulation import benchmark_nav

ROOT = Path(__file__).resolve().parents[1]


class BaselineTests(unittest.TestCase):
    def test_published_gross_and_benchmark(self):
        out = ROOT/'aligned_method/validated_strategy'
        prices = pd.read_csv(out/'diagnostic_prices.csv', index_col=0, parse_dates=True)
        weights = pd.read_csv(out/'frozen_weights.csv', index_col=0).weight
        saved = pd.read_csv(out/'diagnostic_nav.csv', index_col=0, parse_dates=True)
        result = run_path(prices[weights.index], weights, [])
        np.testing.assert_allclose(result['nav'].gross_nav/5e6, saved['Portfolio gross'], atol=1e-9)
        np.testing.assert_allclose(benchmark_nav(prices, 100), saved['Fund X proxy'], atol=1e-9)

    def test_recording_does_not_change_accounting(self):
        dates = pd.bdate_range('2026-05-01', periods=10)
        prices = pd.DataFrame({'a':np.arange(100,110), 'b':np.arange(100,90,-1)}, index=dates)
        weights = pd.Series({'a':.8,'b':-.2})
        a = run_path(prices, weights, [dates[5]], record=True)
        b = run_path(prices, weights, [dates[5]], record=False)
        pd.testing.assert_frame_equal(a['nav'], b['nav'])


if __name__ == '__main__':
    unittest.main()
