"""Separate training and evaluation access with strict common calendars."""
from pathlib import Path
import numpy as np
import pandas as pd
import exchange_calendars as xcals

ROOT = Path(__file__).resolve().parents[1]


def load_joint(stage):
    if stage not in ('training','evaluation'):
        raise ValueError('stage must be training or evaluation')
    base = 'data/rebalancing_training.csv' if stage=='training' else 'aligned_method/validated_strategy/diagnostic_prices.csv'
    frame = pd.read_csv(ROOT/base, index_col=0, parse_dates=True)
    instruments = pd.read_csv(ROOT/f'data/hedging/{stage}_instruments.csv', index_col=0, parse_dates=True)
    start,end = ('2024-04-29','2026-04-28') if stage=='training' else ('2026-05-01','2026-08-03')
    dates = xcals.get_calendar('XNYS').sessions_in_range(start,end).tz_localize(None)
    for panel in [frame,instruments]:
        if not panel.index.equals(dates) or panel.columns.has_duplicates:
            raise ValueError('Require complete unique common XNYS sessions; no filling')
        if not np.isfinite(panel.values).all() or (panel.values<=0).any():
            raise ValueError('Invalid or missing prices')
    if set(frame.columns)&set(instruments.columns):
        raise ValueError('Duplicate instrument labels')
    return pd.concat([frame,instruments],axis=1)
