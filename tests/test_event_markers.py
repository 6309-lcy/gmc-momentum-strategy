import unittest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from rebalancing.event_markers import add_event_flags, scheduled_events


class EventMarkerTests(unittest.TestCase):
    def test_flags_match_events_and_buy_hold_has_none(self):
        dates=pd.date_range('2026-05-01',periods=6)
        policy={'rebalance_dates':[dates[2]],'daily_dates':dates[1:-1], 'weekly_dates':[dates[4]]}
        fig,ax=plt.subplots()
        try:
            for strategy in ['P0','P2','B0']:
                self.assertIsNone(add_event_flags(ax,dates,range(6),scheduled_events(policy,strategy),'blue'))
            self.assertEqual(len(ax.collections),0)
            flags=add_event_flags(ax,dates,range(6),scheduled_events(policy,'P4'),'red',gid='daily-flags')
            self.assertEqual(len(flags.get_offsets()),4)
            self.assertEqual(flags.get_gid(),'daily-flags')
            self.assertEqual(flags.get_offsets()[:,1].tolist(),[1,2,3,4])
        finally:plt.close(fig)

    def test_monthly_and_weekly_have_distinct_dates(self):
        p={'rebalance_dates':['2026-06-01','2026-07-01'],'daily_dates':[], 'weekly_dates':['2026-05-08']}
        self.assertEqual(scheduled_events(p,'P1'),p['rebalance_dates'])
        self.assertEqual(scheduled_events(p,'P5'),p['weekly_dates'])


if __name__=='__main__':unittest.main()
