import unittest
import numpy as np
import pandas as pd
from rebalancing.simulation import joint_indices, paired_comparisons, benchmark_nav, summarize


class SimulationTests(unittest.TestCase):
    def test_reproducible_contiguous_blocks(self):
        a = joint_indices(100, 63, 50, 5, 42)
        np.testing.assert_array_equal(a, joint_indices(100, 63, 50, 5, 42))
        self.assertEqual(a.shape, (50, 63))
        for start in range(0, 60, 5):
            np.testing.assert_array_equal(np.diff(a[:, start:start+5], axis=1), np.ones((50, 4)))

    def test_paired_differences_match_scenario_ids(self):
        frame = pd.DataFrame({'path':[0,1,1,0], 'strategy':['P0','P0','P1','P1'],
                              'net_return':[.1,.2,.23,.11], 'status':['configured']*4})
        self.assertAlmostEqual(paired_comparisons(frame).iloc[0].mean_difference, .02)

    def test_failed_paths_do_not_produce_survivor_statistics(self):
        frame = pd.DataFrame([
            {'path':0,'strategy':'B0','net_return':0.,'status':'configured'},
            {'path':1,'strategy':'B0','net_return':0.,'status':'configured'},
            {'path':0,'strategy':'P0','net_return':.1,'status':'configured'},
            {'path':1,'strategy':'P0','status':'execution_failed'},
            {'path':0,'strategy':'P1','net_return':.2,'status':'configured'},
            {'path':1,'strategy':'P1','net_return':.2,'status':'configured'}])
        for key in ['max_drawdown','turnover','transaction_cost','borrow_cost']:
            frame[key] = 0.
        summary = summarize(frame, {}).set_index('strategy')
        self.assertTrue(np.isnan(summary.loc['P0','mean_net_return']))
        self.assertTrue(np.isnan(summary.loc['P0','loss_frequency']))
        self.assertEqual(summary.loc['P0','failed_scenarios'],1)
        pairs = paired_comparisons(frame)
        self.assertEqual(pairs.iloc[0].excluded_scenarios,1)

    def test_fixed_benchmark_weights_are_enforced(self):
        from rebalancing.data_access import load_config, validate_config
        config = load_config()
        config['benchmark_weights'] = {'URTH':1.,'BNDW':0.,'^SPGSCI':0.}
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_daily_benchmark_rebalances(self):
        p = pd.DataFrame({'^SPGSCI':[100,110,99], 'URTH':[100,100,100], 'BNDW':[100,100,100]})
        self.assertAlmostEqual(benchmark_nav(p, 100).iloc[-1],100*1.02*.98)

    def test_all_assets_share_sampled_dates(self):
        returns = np.column_stack([np.arange(100)/10000, np.arange(100)/5000])
        ix = joint_indices(100, 63, 5, 4, 13)
        sampled = returns[ix]
        np.testing.assert_array_equal(sampled[:,:,1], sampled[:,:,0]*2)


if __name__ == '__main__':
    unittest.main()
