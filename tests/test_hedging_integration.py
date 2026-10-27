import json
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from hedging.data_access import load_joint
from hedging.model import fit_model
from rebalancing.accounting import run_path
from run_hedging import evaluate_path

ROOT=Path(__file__).resolve().parents[1]


class HedgingIntegrationTests(unittest.TestCase):
    def test_stock_ledger_is_unchanged_and_combined_accounts_reconcile(self):
        config=json.loads((ROOT/'hedging/config.json').read_text())
        weights=pd.read_csv(ROOT/'aligned_method/validated_strategy/frozen_weights.csv',index_col=0).weight
        training=load_joint('training'); prices=load_joint('evaluation')
        model=fit_model(training,weights)
        results,stock,signals=evaluate_path(prices,weights,model,config,record=True)
        independent=run_path(prices[weights.index],weights,[],capital=5e8)
        pd.testing.assert_frame_equal(stock['nav'],independent['nav'])
        for result in results.values():
            np.testing.assert_allclose(result['combined_nav'],stock['nav'].nav+result['overlay']['nav'].nav)
        repeated,again,_=evaluate_path(prices,weights,model,config,record=True)
        for name in results:
            pd.testing.assert_series_equal(results[name]['combined_nav'],repeated[name]['combined_nav'])
        self.assertEqual(len(signals),64)
        self.assertEqual(training.shape,(501,18))


if __name__=='__main__':unittest.main()
