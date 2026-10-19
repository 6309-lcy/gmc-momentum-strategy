"""Verify saved accounting and regenerate README figures without network access.

Run with: python report.py
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'aligned_method' / 'validated_strategy'
plt.rcParams.update({'svg.fonttype': 'none', 'svg.hashsalt': 'gmc',
                     'font.family': 'DejaVu Sans', 'axes.spines.top': False,
                     'axes.spines.right': False, 'figure.facecolor': 'white'})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, bbox_inches='tight', metadata={'Date': None})
    plt.close(fig)


def verify_period(weights, prices_name, nav_name, score_name, attribution_name):
    prices = pd.read_csv(OUT / prices_name, index_col=0, parse_dates=True)
    saved_nav = pd.read_csv(OUT / nav_name, index_col=0, parse_dates=True)
    score = pd.read_csv(OUT / score_name, index_col=0)
    growth = prices[weights.index] / prices[weights.index].iloc[0]
    gross = 100 * (1 - weights.sum() + growth @ weights)
    borrow = .02 * (-weights.clip(upper=0).sum()) * np.arange(len(prices)) / 252
    net = gross - 100 * (.001 * weights.abs().sum() + borrow)
    net.iloc[-1] -= 100 * .001 * (weights.abs() * growth.iloc[-1]).sum()
    proxy_weights = pd.Series({'^SPGSCI': .2, 'URTH': .5, 'BNDW': .3})
    proxy_returns = (prices[proxy_weights.index].pct_change(fill_method=None) * proxy_weights).sum(axis=1)
    recomputed = pd.DataFrame({'Portfolio gross': gross,
                              'Portfolio assumed-cost net': net,
                              'Fund X proxy': 100 * (1 + proxy_returns).cumprod()})
    assert recomputed.index.equals(saved_nav.index)
    np.testing.assert_allclose(recomputed, saved_nav, rtol=1e-10, atol=1e-10)
    for name in recomputed:
        nav = recomputed[name].copy()
        nav.iloc[0] = 100
        returns = nav.pct_change().dropna()
        total = recomputed[name].iloc[-1] / 100 - 1
        expected = [total, total * 500, returns.std() * np.sqrt(252), (nav / nav.cummax() - 1).min()]
        actual = score.loc[name, ['Return', 'P&L ($m)', 'Annual volatility', 'Max drawdown']].values
        np.testing.assert_allclose(expected, actual, rtol=1e-9, atol=1e-10)
    attribution = pd.read_csv(OUT / attribution_name, index_col=0)
    pnl = weights * (growth.iloc[-1] - 1) * 500
    np.testing.assert_allclose(pnl.reindex(attribution.index), attribution['P&L ($m)'], atol=1e-9)
    np.testing.assert_allclose(pnl.sum(), score.loc['Portfolio gross', 'P&L ($m)'], atol=1e-9)
    print(f'Verified {len(prices)-1} return intervals: NAV, costs, benchmark, metrics, holding P&L')
    return recomputed, attribution


def main():
    manifest = json.loads((OUT / 'frozen_strategy.json').read_text())
    assert hashlib.sha256((OUT / 'frozen_weights.csv').read_bytes()).hexdigest() == manifest['weights_sha256']
    weights = pd.read_csv(OUT / 'frozen_weights.csv', index_col=0).iloc[:, 0]
    holdings = pd.read_csv(OUT / 'initial_portfolio.csv', index_col=0)
    np.testing.assert_allclose(weights.reindex(holdings.index), holdings.Weight)
    assert np.isclose(weights.abs().sum(), 1)
    assert np.isclose(weights.clip(lower=0).sum(), .8)
    assert np.isclose(-weights.clip(upper=0).sum(), .2)
    assert weights.abs().between(.05 - 1e-9, .15 + 1e-9).all()
    assert (holdings.groupby('Sector').Weight.apply(lambda x: x.abs().sum()) <= .45 + 1e-9).all()
    board = pd.read_csv(OUT / 'validation_leaderboard.csv')
    chosen = board.sort_values('Selection score', ascending=False).iloc[0]
    assert chosen.Rule == manifest['rule'] and chosen['Risk penalty'] == manifest['risk_penalty']
    folds = pd.read_csv(OUT / 'validation_folds.csv')
    assert (pd.to_datetime(folds['Train end']) < pd.to_datetime(folds['Test end'])).all()
    assert pd.to_datetime(folds['Test end']).max() <= pd.Timestamp(manifest['cutoff'])
    data = pd.concat(pd.read_csv(path, index_col=0, parse_dates=True) for path in sorted((ROOT / 'data').glob('training_prices_*.csv')))
    assert data.index.max() == pd.Timestamp(manifest['cutoff'])
    print('Verified weight hash, allocation constraints, model selection, and training cutoff')
    short, _ = verify_period(weights, 'diagnostic_prices.csv', 'diagnostic_nav.csv',
                              'diagnostic_scorecard.csv', 'diagnostic_attribution.csv')
    extended, attribution = verify_period(weights, 'prices_to_9_oct.csv', 'nav_to_9_oct.csv',
                                          'scorecard_to_9_oct.csv', 'attribution_to_9_oct.csv')
    np.testing.assert_allclose(short['Portfolio gross'], extended.loc[short.index, 'Portfolio gross'])

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
    extended.plot(ax=axes[0], title='Frozen momentum portfolio | 1 May–9 October 2026')
    axes[0].set_ylabel('NAV (100 at entry)')
    ((extended / 100 - 1) * 500).plot(ax=axes[1])
    axes[1].set_ylabel('P&L ($ million)')
    # Use pre-cost starting equity as the drawdown reference.
    dd = extended.copy(); dd.iloc[0] = 100
    ((dd / dd.cummax() - 1) * 100).plot(ax=axes[2])
    axes[2].set_ylabel('Drawdown (%)')
    for ax in axes:
        ax.axvline(pd.Timestamp('2026-08-03'), color='grey', ls=':', lw=1)
        ax.grid(alpha=.18); ax.legend(fontsize=8)
    save(fig, 'performance_to_9_oct.svg')

    fig, ax = plt.subplots(figsize=(10, 6))
    values = attribution['P&L ($m)'].sort_values()
    ax.barh(values.index, values, color=['#b54747' if x < 0 else '#227c9d' for x in values])
    ax.axvline(0, color='grey', lw=1)
    ax.set(xlabel='Contribution to gross P&L ($ million)', title='Holding contributions through 9 October 2026')
    save(fig, 'attribution_to_9_oct.svg')

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    board = board.sort_values('Selection score')
    labels = [f"{r.Rule.replace('momentum_stability_analogy', 'Momentum + stability + analogy').replace('momentum_stability', 'Momentum + stability').replace('momentum', 'Momentum')} | penalty {r['Risk penalty']:g}" for _, r in board.iterrows()]
    axes[0].barh(labels, board['Selection score'], color='#227c9d')
    axes[0].set(title='Chronological validation: selection scores', xlabel='Annual mean return minus 2 × variance')
    values = weights.sort_values() * 100
    axes[1].barh(values.index, values, color=['#b54747' if x < 0 else '#227c9d' for x in values])
    axes[1].axvline(0, color='grey', lw=1)
    axes[1].set(title='Initial portfolio', xlabel='Signed weight (%)')
    save(fig, 'validation_and_weights.svg')

    summary = pd.read_csv(OUT / 'mc_summary.csv', index_col=0).iloc[:, 0]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    short.plot(ax=axes[0], title='Three-month diagnostic | 1 May–3 August 2026')
    axes[0].set_ylabel('NAV (100 at entry)')
    low, high = summary['5th percentile'] * 100, summary['95th percentile'] * 100
    axes[1].hlines(0, low, high, color='#227c9d', lw=6, label='Forecast 5th–95th percentiles')
    axes[1].plot(summary['Median return'] * 100, 0, 'o', color='black', label='Forecast median')
    axes[1].plot(summary['Mean return'] * 100, 0, 'D', color='#227c9d', label='Forecast mean')
    axes[1].plot(short['Portfolio gross'].iloc[-1] - 100, 0, 's', color='#b54747', label='Diagnostic gross outcome')
    axes[1].set(title='63-return forecast and observed outcome', xlabel='Return (%)', yticks=[], ylim=(-1, 1))
    axes[1].legend(fontsize=8, loc='upper left')
    save(fig, 'forecast_vs_diagnostic.svg')
    print('Generated four SVG figures for the README and methodology')


if __name__ == '__main__':
    main()
