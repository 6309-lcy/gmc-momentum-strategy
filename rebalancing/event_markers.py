"""Rebalance execution-date flags attached to the corresponding portfolio line."""
import numpy as np
import pandas as pd
from matplotlib.path import Path

FLAG = Path([(0., -1.), (0., 1.), (1., .65), (0., .3), (0., -1.)],
            [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.LINETO])


def add_event_flags(ax, dates, values, event_dates, color, label=None, gid=None):
    dates = pd.DatetimeIndex(dates)
    events = pd.DatetimeIndex(event_dates)
    mask = dates.isin(events)
    if not mask.any():
        return None
    flags = ax.scatter(dates[mask], np.asarray(values)[mask], marker=FLAG, s=42,
                       color=color, linewidths=.8, zorder=5, label=label)
    if gid:
        flags.set_gid(gid)
    return flags


def scheduled_events(policy, strategy):
    # Buy-and-hold and the daily-rebalanced reference benchmark have no stock rebalance flags.
    if strategy in ('P1', 'P3'):
        return policy['rebalance_dates']
    if strategy == 'P4':
        return policy['daily_dates']
    if strategy == 'P5':
        return policy['weekly_dates']
    return []
