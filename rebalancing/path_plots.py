"""Joint-bootstrap price and estimated-risk fans, with saved net portfolio paths."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from .risk_model import complete_returns, covariance
from .simulation import joint_indices
from .event_markers import add_event_flags, scheduled_events


NOTE = ('Shading: per-date 5th–95th percentiles; solid line: per-date median. '
        'Quantile curves are not individual paths.\n'
        'Thin lines: the first five deterministic bootstrap paths (IDs 0–4), '
        'not selected outcomes.')
STRATEGIES = {'P0': 'P0: buy and hold', 'P1': 'P1: monthly',
              'P4': 'P4: daily', 'P5': 'P5: weekly'}


def _asset_paths(training, policy, config):
    tickers = list(policy['weights'])
    if not tickers or len(tickers) > 12:
        raise ValueError('Asset panels require between one and twelve holdings')
    cutoff = policy.get('cutoff', config.get('cutoff'))
    if cutoff is not None and training.index.max() > pd.Timestamp(cutoff):
        raise ValueError('Training contains post-cutoff prices')
    returns = complete_returns(training, list(training.columns))
    dates = pd.DatetimeIndex(policy['session_dates'])
    if dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('Session dates must be unique and ordered')
    decay = config.get('risk_ewma_decay', .94)
    if not np.isfinite(decay) or not 0 <= decay <= 1:
        raise ValueError('risk_ewma_decay must be between zero and one')
    indices = joint_indices(len(returns), len(dates) - 1, policy['n_paths'],
                            policy['block_length'], policy['seed'])
    # Reuse the return cube for price levels after extracting EWMA summaries.
    paths = np.empty((len(indices), len(dates), len(tickers)), dtype=float)
    paths[:, 1:] = returns[tickers].to_numpy()[indices]
    variance = np.broadcast_to(np.diag(covariance(training, tickers)),
                               (len(indices), len(tickers))).copy()
    quantiles = np.empty((3, len(dates), len(tickers)))
    examples = np.empty((min(5, len(indices)), len(dates), len(tickers)))
    for time in range(len(dates)):
        if time:
            variance *= decay
            variance += (1 - decay) * np.square(paths[:, time]) * 252
        volatility = np.sqrt(variance)
        quantiles[:, time] = np.quantile(volatility, [.05, .5, .95], axis=0)
        examples[:, time] = volatility[:5]
    paths[:, 0] = 0.
    paths += 1.
    np.cumprod(paths, axis=1, out=paths)
    paths *= training.iloc[-1][tickers].to_numpy(dtype=float)
    prices = np.quantile(paths, [.05, .5, .95], axis=0)
    frame = pd.DataFrame({'date': np.repeat(dates, len(tickers)),
                          'ticker': np.tile(tickers, len(dates))})
    for metric, values in [('price', prices), ('volatility', quantiles)]:
        for i, suffix in enumerate(('q05', 'q50', 'q95')):
            frame[f'{metric}_{suffix}'] = values[i].reshape(-1)
    return frame, paths[:5].copy(), examples


def _date_axis(ax):
    locator = mdates.AutoDateLocator(minticks=3, maxticks=5)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(alpha=.2)


def _fan(ax, dates, group, columns, label=None, color='C0'):
    ax.fill_between(dates, group[columns[0]].to_numpy(dtype=float),
                    group[columns[2]].to_numpy(dtype=float), color=color, alpha=.15)
    ax.plot(dates, group[columns[1]], color=color, label=label, linewidth=1.5)


def _save(fig, out, stem):
    try:
        with matplotlib.rc_context({'svg.fonttype': 'none'}):
            svg = out / f'{stem}.svg'
            fig.savefig(svg, metadata={'Date': None})
            svg.write_text('\n'.join(line.rstrip() for line in
                                     svg.read_text(encoding='utf-8').splitlines()) + '\n',
                           encoding='utf-8')
            fig.savefig(out / f'{stem}.png', dpi=150)
    finally:
        plt.close(fig)


def _asset_figure(frame, examples, tickers, out, metric):
    fig, axes = plt.subplots(3, 4, figsize=(17, 11), squeeze=False)
    risk = metric == 'volatility'
    for i, ax in enumerate(axes.flat):
        if i >= len(tickers):
            ax.set_visible(False)
            continue
        group = frame[frame.ticker == tickers[i]].sort_values('date')
        dates = pd.DatetimeIndex(group.date)
        _fan(ax, dates, group, [f'{metric}_{q}' for q in ('q05', 'q50', 'q95')])
        ax.plot(dates, examples[:, :, i].T, linewidth=.65, alpha=.4, color='C0')
        ax.set(title=tickers[i], ylabel=('Annualized estimated volatility' if risk
                                       else 'Adjusted-close price'))
        if risk:
            ax.yaxis.set_major_formatter(PercentFormatter(1))
        _date_axis(ax)
    fig.suptitle('Asset annualized estimated volatility (LW initialization; EWMA updates)'
                 if risk else 'Joint-bootstrap asset prices')
    fig.text(.5, .015, NOTE, ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .96))
    _save(fig, out, 'asset_risk_simulation' if risk else 'asset_price_simulation')


def _portfolio_figure(out, policy=None):
    quantile_file = out / 'simulation_path_quantiles.csv'
    example_file = out / 'simulation_path_examples.csv'
    quantiles = pd.read_csv(quantile_file, parse_dates=['date']) if quantile_file.exists() else None
    examples = pd.read_csv(example_file, parse_dates=['date']) if example_file.exists() else None
    fig, axes = plt.subplots(3, 1, figsize=(13, 12), sharex=True)
    for ax, metric, title in zip(axes, ('nav', 'volatility', 'drawdown'),
                               ('Net NAV', 'Annualized estimated volatility', 'Net NAV drawdown')):
        available = False
        missing = []
        for i, (strategy, label) in enumerate(STRATEGIES.items()):
            color = f'C{i}'
            group = (quantiles[(quantiles.strategy == strategy) & (quantiles.metric == metric)]
                     .sort_values('date') if quantiles is not None else pd.DataFrame())
            if not group.empty:
                _fan(ax, pd.DatetimeIndex(group.date), group, ['q05', 'q50', 'q95'], label, color)
                if policy is not None:
                    add_event_flags(ax, group.date, group.q50, scheduled_events(policy, strategy), color,
                                    gid=f'{metric}-{strategy}-median-rebalance-flags')
                available = True
            else:
                missing.append(strategy)
            if examples is not None:
                selected = examples[(examples.strategy == strategy) &
                                    (examples.metric == metric) & examples.path.isin(range(5))]
                for path_id, path in selected.groupby('path'):
                    path = path.sort_values('date')
                    ax.plot(path.date, path.value, color=color, linewidth=.65, alpha=.35)
                    if policy is not None:
                        add_event_flags(ax, path.date, path.value, scheduled_events(policy, strategy), color,
                                        gid=f'{metric}-{strategy}-path-{path_id}-rebalance-flags')
        ax.set(ylabel=title)
        if metric != 'nav':
            ax.yaxis.set_major_formatter(PercentFormatter(1))
        if available:
            ax.legend(loc='best', ncol=2)
        if missing:
            ax.text(.01, .02, 'Saved quantiles unavailable: ' + ', '.join(missing),
                    transform=ax.transAxes, fontsize=9)
        _date_axis(ax)
    fig.suptitle('Joint-bootstrap portfolio paths | flags = scheduled rebalance executions')
    fig.text(.5, .015, NOTE, ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .065, 1, .96))
    figures = out/'figures'
    figures.mkdir(exist_ok=True)
    _save(fig, figures, 'portfolio_simulation')


def write_path_plots(training, policy, config, out):
    """Write fans and asset quantiles without rerunning portfolio accounting.

    Asset scenarios use the simulation's frozen seed and joint block indices.
    Portfolio fans consume simulation_path_quantiles.csv and, when available,
    simulation_path_examples.csv. Missing summaries are labeled in the figure.
    Risk is annualized estimated volatility, updated from the same asset returns;
    it is not an independent random risk forecast. Example IDs 0–4 are fixed by
    bootstrap order; quantiles are marginal at each timestamp, not whole paths.
    """
    out = Path(out)
    frame, prices, volatility = _asset_paths(training, policy, config)
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / 'asset_path_quantiles.csv', index=False, date_format='%Y-%m-%d')
    tickers = list(policy['weights'])
    figures = out/'figures'
    figures.mkdir(exist_ok=True)
    _asset_figure(frame, prices, tickers, figures, 'price')
    _asset_figure(frame, volatility, tickers, figures, 'volatility')
    _portfolio_figure(out, policy)
    return frame
