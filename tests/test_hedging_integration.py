import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from hedging.data_access import load_joint
from hedging.model import fit_model
from rebalancing.accounting import run_path
from run_hedging import evaluate_path, stock_schedules

ROOT=Path(__file__).resolve().parents[1]


class HedgingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads((ROOT/'hedging/config.json').read_text())
        cls.weights=pd.read_csv(ROOT/'aligned_method/validated_strategy/frozen_weights.csv',index_col=0).weight
        cls.training=load_joint('training'); cls.prices=load_joint('evaluation')
        cls.model=fit_model(cls.training,cls.weights)

    def test_each_stock_ledger_matches_original_rebalancing_engine(self):
        results,stocks,signals=evaluate_path(self.prices,self.weights,self.model,self.config,record=True)
        self.assertEqual(len(results),12)
        for frequency,schedule in stock_schedules(self.prices.index).items():
            independent=run_path(self.prices[self.weights.index],self.weights,schedule,capital=5e8)
            pd.testing.assert_frame_equal(stocks[frequency]['nav'],independent['nav'])
            for hedge in ['H0','H1','H2']:
                result=results[f'{frequency}_{hedge}']
                pd.testing.assert_frame_equal(result['stock']['trades'],independent['trades'])
                np.testing.assert_allclose(result['combined_nav'],independent['nav'].nav+result['overlay']['nav'].nav)
        self.assertEqual(len(signals),64)
        self.assertEqual(self.training.shape,(501,18))

    def test_schedules_and_reproducibility(self):
        schedules=stock_schedules(self.prices.index)
        self.assertEqual(schedules['M'],list(pd.to_datetime(['2026-06-01','2026-07-01'])))
        self.assertEqual(schedules['W'],self.prices.index[5:-1:5].tolist())
        self.assertEqual(len(schedules['D']),62)
        a,_,_=evaluate_path(self.prices,self.weights,self.model,self.config)
        b,_,_=evaluate_path(self.prices,self.weights,self.model,self.config)
        for name in a:
            pd.testing.assert_series_equal(a[name]['combined_nav'],b[name]['combined_nav'])
        for hedge in ['H0','H1','H2']:
            pd.testing.assert_frame_equal(a[f'BH_{hedge}']['overlay']['nav'],a[f'M_{hedge}']['overlay']['nav'])

    def test_future_prices_cannot_change_earlier_stock_or_hedge_orders(self):
        changed=self.prices.copy(); changed.iloc[35:]*=1.01
        a,_,_=evaluate_path(self.prices,self.weights,self.model,self.config,record=True)
        b,_,_=evaluate_path(changed,self.weights,self.model,self.config,record=True)
        cutoff=self.prices.index[34]
        for name in a:
            for account in ['stock','overlay']:
                left=a[name][account]['orders']; right=b[name][account]['orders']
                pd.testing.assert_frame_equal(left[left.date<=cutoff].reset_index(drop=True),
                                              right[right.date<=cutoff].reset_index(drop=True))


if __name__=='__main__':unittest.main()
