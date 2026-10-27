"""Joint contiguous-block resampling; every policy receives identical prices."""
import hashlib
import numpy as np
import pandas as pd
from .accounting import run_path

BENCHMARK = {'^SPGSCI': .2, 'URTH': .5, 'BNDW': .3}


def joint_indices(n_observations, horizon, n_paths, block_length, seed):
    if not (1 <= block_length <= n_observations) or horizon < 1 or n_paths < 1:
        raise ValueError('Invalid bootstrap dimensions')
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n_observations - block_length + 1,
                          size=(n_paths, (horizon + block_length - 1) // block_length))
    return (starts[..., None] + np.arange(block_length)).reshape(n_paths, -1)[:, :horizon]


def strategies(policy):
    original = pd.Series(policy['weights'], dtype=float)
    risk = policy.get('risk_weights')
    dates = pd.DatetimeIndex(policy['session_dates'])
    return {'P0': (original, []), 'P1': (original, policy['rebalance_dates']),
            'P2': (pd.Series(risk, dtype=float), []) if risk is not None else None,
            'P3': (pd.Series(risk, dtype=float), policy['rebalance_dates']) if risk is not None else None,
            'P4': (original, policy.get('daily_dates', dates[1:-1].tolist())),
            'P5': (original, policy.get('weekly_dates', dates[5:-1:5].tolist())),
            'P6': (original, []) if policy.get('dynamic_risk_budget') is not None else None,
            'P7': (original, []) if policy.get('loss_drawdown_threshold') is not None else None}


def decision_policy(name, policy):
    if name == 'P6':
        return {'mode': 'risk', 'threshold': policy['dynamic_risk_budget']}
    if name == 'P7':
        return {'mode': 'loss', 'threshold': policy['loss_drawdown_threshold'],
                'reduction_factor': policy['loss_reduction_factor']}
    return None


def unconfigured_reason(name):
    if name == 'P6':
        return 'unconfigured: dynamic risk budget required'
    if name == 'P7':
        return 'unconfigured: drawdown threshold and reduction factor required'
    return 'unconfigured: initial risk budget required'


def benchmark_nav(prices, capital):
    returns = prices[list(BENCHMARK)].pct_change(fill_method=None).iloc[1:]
    daily = returns @ pd.Series(BENCHMARK)
    return pd.Series(np.r_[capital, capital * (1 + daily).cumprod().values], index=prices.index)


def path_metrics(nav, capital, benchmark=None):
    values = np.asarray(nav, dtype=float)
    # Include starting equity before entry fees in drawdown and first-period return.
    extended = np.r_[capital, values]
    daily = values[1:] / values[:-1] - 1
    if len(daily):
        daily[0] = values[1] / capital - 1
    result = {'net_return': values[-1] / capital - 1,
              'max_drawdown': np.min(extended / np.maximum.accumulate(extended) - 1),
              'realized_volatility': np.std(daily, ddof=1) * np.sqrt(252)}
    if benchmark is not None:
        b = np.asarray(benchmark)
        bd = b[1:] / b[:-1] - 1
        result['excess_return'] = result['net_return'] - (b[-1] / capital - 1)
        result['tracking_error'] = np.std(daily - bd, ddof=1) * np.sqrt(252)
    return result


def simulate(training, policy, config):
    dates = pd.DatetimeIndex(policy['session_dates'])
    returns = training.pct_change(fill_method=None).iloc[1:]
    if returns.isna().any().any() or not np.isfinite(returns.values).all():
        raise ValueError('Joint simulation requires complete aligned training returns')
    indices = joint_indices(len(returns), len(dates)-1, policy['n_paths'],
                            policy['block_length'], policy['seed'])
    rows = []
    from .adaptive import causal_covariances
    from pathlib import Path
    configured = {name: spec for name, spec in strategies(policy).items() if spec is not None}
    path_values = {name: np.full((policy['n_paths'], len(dates), 3), np.nan, dtype=np.float32) for name in configured}
    stocks = list(policy['weights'])
    train_stocks = training[stocks]
    kwargs = dict(capital=config['capital'], trading_cost=config['trading_cost'],
                  borrow_rate=config['borrow_rate'], record=False)
    for path, sampled in enumerate(indices):
        levels = np.vstack([np.ones(training.shape[1]),
                            np.cumprod(1 + returns.values[sampled], axis=0)]) * training.iloc[-1].to_numpy()
        prices = pd.DataFrame(levels, index=dates, columns=training.columns)
        covariances = causal_covariances(train_stocks, prices[stocks], config.get('risk_ewma_decay', .94))
        benchmark = benchmark_nav(prices, config['capital'])
        rows.append({'path': path, 'strategy': 'B0', **path_metrics(benchmark, config['capital']),
                     'turnover': 0., 'transaction_cost': 0., 'borrow_cost': 0., 'status': 'configured'})
        for name, specification in strategies(policy).items():
            if specification is None:
                continue
            weights, schedule = specification
            try:
                result = run_path(prices[weights.index], weights, schedule,
                                  decision_policy=decision_policy(name, policy),
                                  risk_covariances=covariances, **kwargs)
                risk_history = result['risk_history']
                path_values[name][path, :, 0] = result['nav']['nav'].to_numpy()/config['capital']*100
                path_values[name][path, :, 1] = risk_history['volatility'].to_numpy()
                path_values[name][path, :, 2] = risk_history['drawdown'].to_numpy()
                nav = result['nav']
                liquidated = nav['nav'].copy()
                liquidated.iloc[-1] = nav['liquidation_nav'].iloc[-1]
                costs = float(nav['transaction_cost'].sum())
                terminal_cost = float(nav['nav'].iloc[-1] - nav['liquidation_nav'].iloc[-1])
                rows.append({'path': path, 'strategy': name,
                             **path_metrics(liquidated, config['capital'], benchmark),
                             'turnover': float(nav['turnover'].sum()) + result['terminal_notional']/float(nav['nav'].iloc[-1]),
                             'transaction_cost': costs,
                             'terminal_liquidation_cost': terminal_cost,
                             'borrow_cost': float(nav['borrow_cost'].sum()), 'status': 'configured'})
            except ValueError as exc:
                # Preserve failed scenarios explicitly; never condition summaries on survival silently.
                rows.append({'path': path, 'strategy': name, 'status': 'execution_failed', 'warning': str(exc)})
        if (path + 1) % 1000 == 0:
            print(f'Completed {path+1}/{len(indices)} paired bootstrap scenarios', flush=True)
    out = Path(config.get('output_dir', 'aligned_method/rebalancing'))
    out.mkdir(parents=True, exist_ok=True)
    quantile_rows, example_rows = [], []
    for name, values in path_values.items():
        complete = np.isfinite(values).all(axis=(1, 2))
        # Suppress unconditional bands when any scenario has an undefined financing outcome.
        bands = np.quantile(values, [.05, .5, .95], axis=0) if complete.all() else np.full((3, len(dates), 3), np.nan)
        for t, date in enumerate(dates):
            for m, metric in enumerate(['nav', 'volatility', 'drawdown']):
                quantile_rows.append({'date': date, 'strategy': name, 'metric': metric,
                                      'q05': bands[0,t,m], 'q50': bands[1,t,m], 'q95': bands[2,t,m],
                                      'failed_scenarios': int((~complete).sum())})
                for path in range(min(20, len(values))):
                    example_rows.append({'path': path, 'date': date, 'strategy': name, 'metric': metric,
                                         'value': values[path,t,m]})
    pd.DataFrame(quantile_rows).to_csv(out/'simulation_path_quantiles.csv', index=False)
    pd.DataFrame(example_rows).to_csv(out/'simulation_path_examples.csv', index=False)
    samples = pd.DataFrame(rows)
    summary = summarize(samples, policy)
    return samples, summary, {'sample_indices_sha256': hashlib.sha256(indices.tobytes()).hexdigest(),
                               'training_return_observations': len(returns)}


def summarize(samples, policy):
    benchmark = samples[samples.strategy == 'B0'].set_index('path').net_return
    rows = []
    for name in ['B0', 'P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']:
        group = samples[samples.strategy == name]
        if group.empty:
            rows.append({'strategy': name, 'status': unconfigured_reason(name)})
            continue
        good = group[group.status == 'configured'].set_index('path')
        r = good.net_return
        excess = r - benchmark.reindex(good.index)
        q = r.quantile(.05)
        rows.append({'strategy': name, 'status': 'configured' if len(good)==len(group) else 'contains execution failures',
                     'scenarios': len(group), 'failed_scenarios': len(group)-len(good),
                     'mean_net_return': r.mean(), 'median_net_return': r.median(),
                     'p05_net_return': q, 'p95_net_return': r.quantile(.95),
                     'mean_excess_return': excess.mean(), 'outperformance_frequency': (excess > 0).sum()/len(group),
                     'loss_frequency': (r < 0).sum()/len(group), 'worst_5pct_mean_return': r[r <= q].mean(),
                     'mean_max_drawdown': good.max_drawdown.mean(),
                     'p05_max_drawdown': good.max_drawdown.quantile(.05),
                     'p95_max_drawdown': good.max_drawdown.quantile(.95),
                     'mean_turnover': good.turnover.mean(), 'mean_transaction_cost': good.transaction_cost.mean(),
                     'mean_terminal_liquidation_cost': good.get('terminal_liquidation_cost', pd.Series(dtype=float)).mean(),
                     'mean_borrow_cost': good.borrow_cost.mean(),
                     'statistics_basis': 'all scenarios' if len(good)==len(group) else 'unconditional statistics unavailable; execution failure outcomes unknown'})
        if len(good) != len(group):
            for key in list(rows[-1]):
                if key.startswith(('mean_', 'median_', 'p05_', 'p95_', 'worst_', 'loss_', 'outperformance_')):
                    rows[-1][key] = np.nan
    return pd.DataFrame(rows)


def paired_comparisons(samples):
    wide = samples[samples.status == 'configured'].pivot(index='path', columns='strategy', values='net_return')
    rows = []
    for title, left, right in [('rebalancing', 'P1', 'P0'), ('initial risk', 'P2', 'P0'),
                                ('risk portfolio rebalancing', 'P3', 'P2'),
                                ('daily rebalancing', 'P4', 'P0'), ('weekly rebalancing', 'P5', 'P0'),
                                ('risk-triggered reduction', 'P6', 'P0'), ('loss-triggered reduction', 'P7', 'P0')]:
        if left not in wide or right not in wide:
            rows.append({'comparison': title, 'status': unconfigured_reason(left)})
            continue
        difference = (wide[left] - wide[right]).dropna()
        expected = samples.path.nunique()
        if len(difference) != expected:
            rows.append({'comparison': title, 'status': 'unavailable: execution failure outcomes unknown',
                         'paired_scenarios': len(difference), 'excluded_scenarios': expected-len(difference)})
            continue
        rows.append({'comparison': title, 'status': 'configured', 'paired_scenarios': len(difference),
                     'mean_difference': difference.mean(), 'median_difference': difference.median(),
                     'p05_difference': difference.quantile(.05), 'p95_difference': difference.quantile(.95),
                     'positive_difference_frequency': (difference > 0).mean()})
    return pd.DataFrame(rows)
