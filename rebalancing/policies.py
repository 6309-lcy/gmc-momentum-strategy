"""Freeze training-only policy decisions before opening diagnostic prices."""
from copy import deepcopy
import hashlib
import json

import numpy as np
import pandas as pd

from .data_access import _sessions, calendar_dates, load_weights, resolve_path, validate_config, validate_prices
from .risk_model import covariance, complete_returns


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _training_hash(training):
    values = pd.util.hash_pandas_object(training, index=True).to_numpy().tobytes()
    return hashlib.sha256(values + json.dumps(list(training.columns)).encode()).hexdigest()


def verify_freeze(policy):
    """Detect any mutation of the returned JSON-compatible policy snapshot."""
    payload = deepcopy(policy)
    expected = payload.pop('freeze_hash')
    if _hash(payload) != expected:
        raise ValueError('Frozen policy hash mismatch')
    return True


def freeze_policy(config, training):
    """Snapshot inputs and choices without reading evaluation prices.

    Block length is one plus the largest significant autocorrelation lag, capped
    at 21, across signed portfolio returns and squared returns (lags 1..20).
    Significance uses 1.96/sqrt(n); no significant lags implies IID blocks of one.
    A supplied risk budget is an annual LW-volatility ceiling implemented by
    scaling all exposures together toward cash, with no increase in leverage.
    """
    config = deepcopy(config)
    validate_config(config)
    training = training.copy(deep=True)
    weights = load_weights(config)
    dates = _sessions(config, config['training_start'], config['cutoff'])
    validate_prices(training, dates, list(weights.index))
    returns = complete_returns(training, list(weights.index))
    portfolio = returns @ weights
    threshold = 1.96 / np.sqrt(len(portfolio))
    significant = []
    for lag in range(1, min(20, len(portfolio) // 4) + 1):
        for series in (portfolio, portfolio ** 2):
            correlation = series.autocorr(lag)
            if np.isfinite(correlation) and abs(correlation) > threshold:
                significant.append(lag)
    block_length = min(21, 1 + max(significant, default=0))
    sessions = calendar_dates(config)
    rebalance = sessions[pd.Series(sessions.to_period('M')).ne(pd.Series(sessions.to_period('M')).shift()).to_numpy()]
    rebalance = rebalance[(rebalance > sessions[0]) & (rebalance < sessions[-1])]
    sector_frame = pd.read_csv(resolve_path(config, 'sectors_path'), index_col=0)
    if sector_frame.index.has_duplicates or not set(weights.index) <= set(sector_frame.index):
        raise ValueError('Initial portfolio must define every holding sector uniquely')
    sectors = sector_frame.loc[weights.index, 'Sector']
    if sectors.isna().any():
        raise ValueError('Missing holding sectors')
    risk_weights = None
    k = None
    if config['risk_budget'] is not None:
        vol = float(np.sqrt(weights.to_numpy() @ covariance(training, weights) @ weights.to_numpy()))
        k = min(1., config['risk_budget'] / vol) if vol > 0 else 1.
        risk_weights = (weights * k).to_dict()
    missing = sorted(set(config['benchmark_weights']) - set(training.columns))
    present = list(weights.index) + [name for name in config['benchmark_weights'] if name in training]
    validate_prices(training, dates, present)
    policy = {
        'weights': weights.to_dict(), 'risk_weights': risk_weights,
        'sectors': sectors.to_dict(), 'k': k, 'cutoff': config['cutoff'],
        'rebalance_dates': rebalance.strftime('%Y-%m-%d').tolist(),
        'session_dates': sessions.strftime('%Y-%m-%d').tolist(),
        'block_length': block_length,
        'block_length_rule': '1 + largest lag with abs(ACF) > 1.96/sqrt(n) in portfolio returns or squared returns, lags 1..20; cap 21',
        'seed': config['seed'], 'n_paths': config['n_paths'],
        'joint_simulation_ready': not missing, 'missing_benchmarks': missing,
        'simulation_block_reason': f'Missing pre-cutoff benchmark history: {missing}' if missing else None,
        'risk_policy_status': 'unconfigured' if k is None else 'configured',
        'training_hash': _training_hash(training),
        'weights_sha256': hashlib.sha256(resolve_path(config, 'weights_path').read_bytes()).hexdigest(),
        'config': config,
    }
    policy['freeze_hash'] = _hash(policy)
    return policy
