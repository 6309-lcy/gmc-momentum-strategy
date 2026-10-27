"""Frozen training estimates and causal volatility/trend hedge states."""
import hashlib
import json

import numpy as np
import pandas as pd


CUTOFF = pd.Timestamp('2026-04-28')


def _digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def _weights(weights):
    if not isinstance(weights, pd.Series) or weights.empty or weights.index.has_duplicates:
        raise ValueError('Weights require a nonempty Series with unique stock labels')
    if not all(isinstance(label, str) for label in weights.index) or 'SPY' in weights.index:
        raise ValueError('Weights must name stocks separately from the SPY market series')
    result = weights.astype(float).copy()
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError('Weights must be finite')
    return result


def _prices(prices, weights, minimum):
    if not isinstance(prices.index, pd.DatetimeIndex) or prices.index.hasnans:
        raise ValueError('Prices require a valid DatetimeIndex')
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing:
        raise ValueError('Prices require unique increasing dates')
    if prices.columns.has_duplicates or len(prices) < minimum:
        raise ValueError(f'Prices require unique columns and at least {minimum} observations')
    columns = list(weights.index) + ['SPY']
    if set(columns) - set(prices.columns):
        raise ValueError('Joint prices must contain every weighted stock and SPY')
    panel = prices.loc[:, columns].astype(float).copy()
    if not np.isfinite(panel.to_numpy()).all() or (panel <= 0).any().any():
        raise ValueError('Joint prices must be complete, finite and positive')
    return panel


def _state(previous, volatility, trend, entry, exit):
    if previous == 'stress':
        return 'normal' if volatility < exit or trend >= 0 else 'stress'
    return 'stress' if volatility > entry and trend < 0 else 'normal'


def fit_model(training, weights, decay=.94):
    """Fit only prices through April 28, 2026; return a detached JSON snapshot.

    The first 21 returns seed a zero-mean daily second moment. Percentiles use
    subsequent annualized EWMA observations. States follow a deterministic
    hysteresis rule, not a hidden Markov model.
    """
    weights = _weights(weights)
    if not np.isfinite(decay) or not 0 < decay < 1:
        raise ValueError('Decay must be strictly between zero and one')
    panel = _prices(training, weights, 23)
    if any(date.date() > CUTOFF.date() for date in panel.index):
        raise ValueError('Training must end on or before 2026-04-28')
    returns = panel.pct_change(fill_method=None).iloc[1:]
    portfolio = (returns.loc[:, weights.index] @ weights).to_numpy()
    market = returns['SPY'].to_numpy()
    variance = float(np.mean(portfolio[:21] ** 2))
    volatilities = [float(np.sqrt(252 * variance))]
    for value in portfolio[21:]:
        variance = float(decay * variance + (1 - decay) * value ** 2)
        volatilities.append(float(np.sqrt(252 * variance)))
    entry, exit = np.quantile(volatilities[1:], [.75, .50])
    market_variance = float(np.var(market, ddof=1))
    if market_variance <= 0:
        raise ValueError('SPY training returns must have positive variance to estimate beta')
    beta_raw = float(np.cov(portfolio, market, ddof=1)[0, 1] / market_variance)
    state = 'normal'
    for end, volatility in enumerate(volatilities, start=21):
        trend = float(np.prod(1 + market[end - 21:end]) - 1)
        state = _state(state, volatility, trend, entry, exit)
    config = {
        'cutoff': '2026-04-28',
        'decay': float(decay),
        'annualization': 252,
        'seed_window': 21,
        'trend_window': 21,
        'entry_quantile': .75,
        'exit_quantile': .50,
        'market': 'SPY',
        'variance_estimator': 'zero_mean_ewma',
        'threshold_sample': 'after_first_21_returns',
        'state_rule': 'enter: volatility > entry and trend < 0; exit: volatility < exit or trend >= 0',
        'portfolio_returns': 'fixed_original_target_weights',
        'beta_bounds': [0., 1.],
    }
    model = {
        'config': config,
        'weights': {label: float(value) for label, value in weights.items()},
        'training_start': panel.index[0].isoformat(),
        'training_end': panel.index[-1].isoformat(),
        'training_observations': len(panel),
        'training_hash': _digest({
            'dates': [date.isoformat() for date in panel.index],
            'columns': list(panel.columns),
            'prices': panel.to_numpy().tolist(),
        }),
        'entry_threshold': float(entry),
        'exit_threshold': float(exit),
        'beta_raw': beta_raw,
        'beta': float(np.clip(beta_raw, 0, 1)),
        'initial_variance': variance,
        'trailing_spy_returns': market[-21:].tolist(),
        'initial_state': state,
    }
    model['freeze_hash'] = _digest(model)
    return model


def filter_states(prices, model, weights):
    """Filter completed evaluation returns without refitting frozen estimates.

    Observation zero uses the final training variance, trend and state. Only
    evaluation price pairs from observation one onward update the filter.
    """
    payload = {key: value for key, value in model.items() if key != 'freeze_hash'}
    if model.get('freeze_hash') != _digest(payload):
        raise ValueError('Model freeze hash mismatch')
    weights = _weights(weights)
    if weights.to_dict() != model['weights']:
        raise ValueError('Evaluation weights must match frozen original target weights')
    panel = _prices(prices, weights, 1)
    if panel.index[0] <= pd.Timestamp(model['training_end']):
        raise ValueError('Evaluation observations must follow the training period')
    config = model['config']
    variance = model['initial_variance']
    trailing = list(model['trailing_spy_returns'])
    state = model['initial_state']
    returns = panel.pct_change(fill_method=None)
    portfolio = returns.loc[:, weights.index] @ weights
    rows = []
    for i in range(len(panel)):
        if i:
            variance = config['decay'] * variance + (1 - config['decay']) * float(portfolio.iloc[i]) ** 2
            trailing = (trailing + [float(returns['SPY'].iloc[i])])[-config['trend_window']:]
        volatility = float(np.sqrt(config['annualization'] * variance))
        trend = float(np.prod(1 + np.asarray(trailing)) - 1)
        if i:
            state = _state(state, volatility, trend, model['entry_threshold'], model['exit_threshold'])
        rows.append((volatility, trend, state, state == 'stress'))
    return pd.DataFrame(rows, index=prices.index.copy(),
                        columns=['volatility', 'trend_21', 'state', 'hedge_active'])
