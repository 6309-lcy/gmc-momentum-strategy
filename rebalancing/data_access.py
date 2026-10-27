"""Strict price boundaries and the fixed XNYS evaluation clock."""
from copy import deepcopy
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def validate_config(config):
    """Validate without changing caller-owned configuration."""
    dates = []
    for key in ('training_start', 'cutoff', 'evaluation_start', 'evaluation_end'):
        value = config[key]
        date = pd.Timestamp(value)
        if not isinstance(value, str) or date.strftime('%Y-%m-%d') != value:
            raise ValueError(f'{key} must be an ISO date')
        dates.append(date)
    if not dates[0] < dates[1] < dates[2] < dates[3]:
        raise ValueError('Require training_start < cutoff < evaluation_start < evaluation_end')
    if config['calendar'] != 'XNYS' or config['price_basis'] != 'adjusted_close':
        raise ValueError('XNYS and adjusted_close are required')
    for key in ('transaction_cost_bps', 'annual_borrow_rate'):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
            raise ValueError(f'{key} must be finite and nonnegative')
    if config['transaction_cost_bps'] > 10000 or config['annual_borrow_rate'] > 1:
        raise ValueError('Costs exceed 100%')
    for key in ('seed', 'n_paths', 'annualization', 'expected_return_intervals'):
        if isinstance(config[key], bool) or not isinstance(config[key], int) or config[key] < (0 if key == 'seed' else 1):
            raise ValueError(f'Invalid {key}')
    budget = config['risk_budget']
    if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float)) or not np.isfinite(budget) or budget <= 0):
        raise ValueError('risk_budget must be null or a positive annual volatility')
    benchmarks = config['benchmark_weights']
    if set(benchmarks) != {'URTH', 'BNDW', '^SPGSCI'} or any(not np.isfinite(v) or v < 0 for v in benchmarks.values()) or not np.isclose(sum(benchmarks.values()), 1):
        raise ValueError('Invalid Fund X benchmark weights')
    if any(not np.isclose(benchmarks[name], value) for name, value in {'URTH': .5, 'BNDW': .3, '^SPGSCI': .2}.items()):
        raise ValueError('Fund X requires fixed 20/50/30 benchmark weights')
    if config.get('capital', 500e6) <= 0 or not np.isfinite(config.get('capital', 500e6)):
        raise ValueError('capital must be positive and finite')
    decay = config.get('risk_ewma_decay', .94)
    if not isinstance(decay, (int, float)) or isinstance(decay, bool) or not 0 < decay < 1:
        raise ValueError('risk_ewma_decay must lie strictly between zero and one')
    for key in ('dynamic_risk_budget', 'loss_drawdown_threshold'):
        value = config.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0):
            raise ValueError(f'{key} must be null or positive')
    loss = config.get('loss_drawdown_threshold')
    factor = config.get('loss_reduction_factor')
    if loss is not None and loss >= 1:
        raise ValueError('loss_drawdown_threshold must be below one')
    if (loss is None) != (factor is None):
        raise ValueError('Loss threshold and reduction factor must be configured together')
    if factor is not None and (isinstance(factor, bool) or not isinstance(factor, (int, float)) or not 0 <= factor < 1):
        raise ValueError('loss_reduction_factor must lie in [0,1)')
    if config['rebalance_frequency'] != 'monthly':
        raise ValueError('Only monthly rebalancing is supported')


def load_config(path=None):
    """Load defaults; relative data paths resolve against the repository root."""
    with open(path or Path(__file__).with_name('config.json'), encoding='utf-8') as stream:
        config = json.load(stream)
    validate_config(config)
    return deepcopy(config)


def resolve_path(config, key):
    path = Path(config[key])
    return path if path.is_absolute() else ROOT / path


def _sessions(config, start, end):
    import exchange_calendars as xcals
    dates = xcals.get_calendar(config['calendar']).sessions_in_range(start, end)
    return dates.tz_localize(None).rename('Date')


def calendar_dates(config):
    validate_config(config)
    dates = _sessions(config, config['evaluation_start'], config['evaluation_end'])
    if dates[0] != pd.Timestamp(config['evaluation_start']) or dates[-1] != pd.Timestamp(config['evaluation_end']):
        raise ValueError('Evaluation endpoints must be XNYS sessions')
    if len(dates) - 1 != config['expected_return_intervals']:
        raise ValueError(f'Expected {config["expected_return_intervals"]} returns; calendar has {len(dates) - 1}')
    return dates


def _read_prices(path):
    frame = pd.read_csv(path, index_col=0)
    frame.index = pd.to_datetime(frame.index, errors='raise').as_unit('ns')
    if frame.index.tz is not None or not frame.index.equals(frame.index.normalize()):
        raise ValueError('Prices require timezone-naive session dates')
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing or frame.columns.has_duplicates:
        raise ValueError('Prices must have unique, ordered dates and unique columns')
    return frame


def validate_prices(frame, dates, columns):
    if not frame.index.equals(dates):
        raise ValueError('Price dates must exactly match the required XNYS sessions; no filling is allowed')
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f'Missing assets: {sorted(missing)}')
    values = frame[list(columns)].to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('Prices must be finite, positive and complete; no filling is allowed')


def load_weights(config):
    weights = pd.read_csv(resolve_path(config, 'weights_path'), index_col=0)['weight']
    if weights.index.has_duplicates or weights.empty or not np.isfinite(weights).all():
        raise ValueError('Invalid frozen weights')
    if not np.isclose(weights.abs().sum(), 1) or not np.isclose(weights.sum(), .6):
        raise ValueError('Frozen momentum weights must have gross 1 and net 0.6')
    return weights


def load_training(config):
    """Reject post-cutoff rows and incomplete joint panels; never impute prices."""
    validate_config(config)
    prices = _read_prices(resolve_path(config, 'training_path'))
    dates = _sessions(config, config['training_start'], config['cutoff'])
    stocks = list(load_weights(config).index)
    validate_prices(prices, dates, stocks)
    present = [name for name in config['benchmark_weights'] if name in prices]
    validate_prices(prices, dates, stocks + present)
    missing = sorted(set(config['benchmark_weights']) - set(present))
    prices = prices[stocks + present].copy()
    prices.attrs.update(cutoff=config['cutoff'], price_basis=config['price_basis'],
                        provenance=config['training_provenance'], missing_benchmarks=missing,
                        joint_simulation_ready=not missing)
    if missing:
        warnings.warn(f'Joint simulation blocked: missing pre-cutoff benchmark history {missing}', RuntimeWarning, stacklevel=2)
    return prices


def load_evaluation(config):
    """Select the diagnostic window and require all fifteen assets on every session."""
    validate_config(config)
    prices = _read_prices(resolve_path(config, 'evaluation_path'))
    prices = prices.loc[config['evaluation_start']:config['evaluation_end']]
    names = list(load_weights(config).index) + list(config['benchmark_weights'])
    validate_prices(prices, calendar_dates(config), names)
    prices = prices[names].copy()
    prices.attrs.update(price_basis='adjusted_close', note=config['evaluation_note'])
    return prices
