"""Historical adjusted-close replay of previously frozen policies."""
import numpy as np
import pandas as pd
from .accounting import run_path
from .simulation import benchmark_nav, strategies, path_metrics


def evaluate(prices, policy, config, samples=None):
    capital = config['capital']
    benchmark = benchmark_nav(prices, capital)
    navs = [pd.DataFrame({'date': prices.index, 'strategy': 'B0', 'nav': benchmark.values,
                         'gross_nav': benchmark.values, 'liquidation_nav': benchmark.values})]
    metrics = [{'strategy': 'B0', 'status': 'proxy benchmark',
                **path_metrics(benchmark, capital), 'gross_return': benchmark.iloc[-1]/capital-1,
                'mtm_net_return': benchmark.iloc[-1]/capital-1}]
    outputs = {key: [] for key in ['orders', 'trades', 'costs', 'attribution', 'daily_positions']}
    for name, specification in strategies(policy).items():
        if specification is None:
            metrics.append({'strategy': name, 'status': 'unconfigured: risk budget required'})
            continue
        weights, schedule = specification
        result = run_path(prices[weights.index], weights, schedule, capital=capital,
                          trading_cost=config['trading_cost'], borrow_rate=config['borrow_rate'])
        nav = result['nav']
        liquidated = nav['nav'].copy()
        liquidated.iloc[-1] = nav['liquidation_nav'].iloc[-1]
        row = {'strategy': name, 'status': 'historical close-price diagnostic',
               **path_metrics(liquidated, capital, benchmark),
               'gross_return': nav['gross_nav'].iloc[-1]/capital-1,
               'mtm_net_return': nav['nav'].iloc[-1]/capital-1,
               'turnover': nav['turnover'].sum() + result['terminal_notional']/float(nav['nav'].iloc[-1]),
               'transaction_cost': nav['transaction_cost'].sum(),
               'terminal_liquidation_cost': nav['nav'].iloc[-1]-nav['liquidation_nav'].iloc[-1],
               'borrow_cost': nav['borrow_cost'].sum()}
        if samples is not None:
            distribution = samples[(samples.strategy == name) & (samples.status == 'configured')].net_return
            all_scenarios = samples[samples.strategy == name]
            row['simulation_percentile'] = float((distribution <= row['net_return']).mean() * 100) if len(distribution) == len(all_scenarios) else np.nan
        metrics.append(row)
        navs.append(nav.rename_axis('date').reset_index().assign(strategy=name))
        for key in outputs:
            frame = result[key].reset_index() if key == 'attribution' else result[key]
            outputs[key].append(frame.assign(strategy=name))
    actual = pd.DataFrame(metrics)
    if samples is not None:
        bdist = samples[samples.strategy == 'B0'].net_return
        actual.loc[actual.strategy == 'B0', 'simulation_percentile'] = (bdist <= actual.iloc[0].net_return).mean()*100
    joined = {key: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
              for key, frames in outputs.items()}
    return {'actual_metrics': actual, 'daily_nav': pd.concat(navs, ignore_index=True), **joined}


def reconcile_baseline(prices, policy, config, evaluation):
    w = pd.Series(policy['weights'])
    growth = prices[w.index]/prices[w.index].iloc[0]
    gross = config['capital'] * (1-w.sum()+growth@w)
    original_borrow = config['capital']*.02*(-w.clip(upper=0).sum())*np.arange(len(prices))/252
    published = gross - config['capital']*.001*w.abs().sum()-original_borrow
    published.iloc[-1] -= config['capital']*.001*(w.abs()*growth.iloc[-1]).sum()
    new = evaluation['daily_nav'].query("strategy == 'P0'").set_index('date')
    np.testing.assert_allclose(new.gross_nav, gross, rtol=1e-12, atol=1e-6)
    saved = pd.read_csv('aligned_method/validated_strategy/diagnostic_nav.csv', index_col=0, parse_dates=True)
    np.testing.assert_allclose(gross/config['capital']*100, saved['Portfolio gross'], atol=1e-9)
    np.testing.assert_allclose(published/config['capital']*100, saved['Portfolio assumed-cost net'], atol=1e-9)
    return pd.DataFrame([{'measure': 'gross_return', 'published': gross.iloc[-1]/config['capital']-1,
                          'standardized': new.gross_nav.iloc[-1]/config['capital']-1},
                         {'measure': 'net_liquidation_return', 'published': published.iloc[-1]/config['capital']-1,
                          'standardized': new.liquidation_nav.iloc[-1]/config['capital']-1}])
