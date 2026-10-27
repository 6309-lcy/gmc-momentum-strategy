"""Pre-cutoff risk diagnostics for fixed signed portfolio exposures."""
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

BENCHMARKS = {'URTH': .5, 'BNDW': .3, '^SPGSCI': .2}


def complete_returns(training, columns):
    """Use one complete common panel, preserving cross-asset dependence."""
    if training.index.has_duplicates or not training.index.is_monotonic_increasing or training.columns.has_duplicates or len(training) < 3:
        raise ValueError('Training requires unique ordered dates and at least three prices')
    missing = set(columns) - set(training.columns)
    if missing:
        raise ValueError(f'Joint simulation blocked: missing pre-cutoff assets {sorted(missing)}')
    prices = training[list(columns)].astype(float)
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError('Training panel must be complete and positive; no filling or pairwise deletion')
    return prices.pct_change(fill_method=None).iloc[1:]


def require_joint_training(training, weights):
    """Return bootstrap-ready joint returns or explicitly block the simulation."""
    return complete_returns(training, list(weights.index if isinstance(weights, pd.Series) else weights) + list(BENCHMARKS))


def covariance(training, weights):
    returns = complete_returns(training, list(weights.index if isinstance(weights, pd.Series) else weights))
    return LedoitWolf().fit(returns.to_numpy()).covariance_ * 252


def diagnostics(training, weights, sectors):
    """Tidy annualized LW risk, exposures, benchmark comparisons and rolling stresses.

    Stress blocks are worst historical compounded constant-weight returns over
    5, 21 and 63 sessions within the supplied training window. Missing benchmark
    metrics are NaN, never proxy substitutes. Risk contributions sum to LW vol.
    """
    weights = pd.Series(weights, dtype=float)
    if weights.empty or not np.isfinite(weights).all():
        raise ValueError('Weights must be finite and nonempty')
    if set(weights.index) - set(sectors):
        raise ValueError('Every holding requires an initial-portfolio sector')
    returns = complete_returns(training, list(weights.index))
    w = weights.to_numpy()
    cov = covariance(training, weights)
    vol = float(np.sqrt(w @ cov @ w))
    portfolio = returns @ weights
    rows = [('lw_volatility', vol), ('gross_exposure', float(weights.abs().sum())),
            ('net_exposure', float(weights.sum())),
            ('long_exposure', float(weights.clip(lower=0).sum())),
            ('short_exposure', float(-weights.clip(upper=0).sum()))]
    gross = weights.abs().sum()
    shares = weights.abs() / gross if gross else weights.abs()
    rows.extend([('holding_hhi', float((shares ** 2).sum())),
                 ('max_holding_gross', float(weights.abs().max()))])
    grouped = weights.abs().groupby(pd.Series({t: sectors[t] for t in weights.index})).sum()
    rows.append(('sector_hhi', float(((grouped / gross) ** 2).sum()) if gross else 0.))
    for sector, exposure in grouped.items():
        rows.append((f'sector_gross:{sector}', float(exposure)))
    for ticker, contribution in zip(weights.index, w * (cov @ w) / vol if vol else np.zeros(len(w))):
        rows.append((f'risk_contribution:{ticker}', float(contribution)))
    for name, benchmark_weights in [('URTH', {'URTH': 1.}), ('FundX', BENCHMARKS)]:
        available = set(benchmark_weights) <= set(training.columns)
        rows.append((f'benchmark_available:{name}', float(available)))
        beta = tracking_error = np.nan
        if available:
            benchmark = complete_returns(training, list(benchmark_weights)) @ pd.Series(benchmark_weights)
            variance = benchmark.var(ddof=1)
            beta = float(portfolio.cov(benchmark) / variance) if variance > 0 else np.nan
            tracking_error = float((portfolio - benchmark).std(ddof=1) * np.sqrt(252))
        rows.extend([(f'beta:{name}', beta), (f'tracking_error:{name}', tracking_error)])
    for length in (5, 21, 63):
        stressed = (1 + portfolio).rolling(length).apply(np.prod, raw=True) - 1
        rows.append((f'stress_worst_{length}_session_return', float(stressed.min())))
    result = pd.DataFrame(rows, columns=['metric', 'value'])
    result.attrs['stress_definition'] = 'Worst rolling compounded constant-weight training returns; no evaluation observations.'
    return result
