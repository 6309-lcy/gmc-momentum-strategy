"""Tables, audit manifest, figures, and standalone research narrative."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_report(out, config, policy, evaluation, summary, pairs, reconciliation, warnings, manifest):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in evaluation.items():
        frame.to_csv(out/f'{name}.csv', index=False)
    summary.to_csv(out/'simulation_summary.csv', index=False)
    pairs.to_csv(out/'paired_comparisons.csv', index=False)
    reconciliation.to_csv(out/'baseline_reconciliation.csv', index=False)
    (out/'run_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (out/'data_quality_report.md').write_text('# Data quality and execution assumptions\n\n' + '\n\n'.join('- '+w for w in warnings), encoding='utf-8')
    figure_dir = out/'figures'
    figure_dir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    for name, group in evaluation['daily_nav'].groupby('strategy'):
        ax.plot(pd.to_datetime(group.date), group.nav/config['capital']*100, label=name)
    ax.set(title='Historical adjusted-close diagnostic | marked-to-market NAV', ylabel='NAV (initial equity = 100)')
    ax.legend(); ax.grid(alpha=.2); fig.autofmt_xdate(); fig.tight_layout()
    fig.savefig(figure_dir/'historical_nav.svg', metadata={'Date': None})
    plt.close(fig)
    text = f'''# Portfolio rebalancing and initial risk positioning

This historical diagnostic compares the frozen momentum portfolio with monthly fixed-target rebalancing. Starting equity is ${config['capital']:,.0f}. Entry uses the 1 May 2026 adjusted close; the endpoint uses the 3 August 2026 adjusted close. There are {len(policy['session_dates'])} valuation observations and {len(policy['session_dates'])-1} close-to-close return intervals on the fixed XNYS calendar.

The monthly execution dates are {', '.join(policy['rebalance_dates'])}. Orders use the preceding session's prices and NAV. Fixed quantities fill at the next scheduled adjusted close. The first portfolio allocation is a same-close idealization. Fractional quantities represent synthetic dividend-adjusted units. These results are idealized close-price diagnostics. Verified opening execution requires a separate coherent open, close, split, and dividend dataset.

## Historical comparison

Primary net returns include entry, actual rebalance trades, daily outstanding-short borrowing, and hypothetical terminal liquidation costs. Marked-to-market returns retain the open positions. Gross returns use a parallel zero-cost ledger with its own causal NAV sizing.

{evaluation['actual_metrics'].to_markdown(index=False, floatfmt='.6f')}

![Historical NAV](figures/historical_nav.svg)

P2 and P3 are relaxed-exposure variants. Their default status is unconfigured because no independently justified volatility budget has been supplied. The pipeline supports a positive predeclared `risk_budget` in the configuration; it freezes the scale before simulation and historical replay. All five predefined strategy IDs remain visible in the output tables.

## Paired historical-bootstrap scenarios

The joint bootstrap draws {policy['n_paths']:,} scenarios with seed {policy['seed']}, using contiguous blocks of {policy['block_length']} daily return observations. Each asset and each strategy receives the same sampled historical dates. The frozen policy records the pre-cutoff block-length rule. This is a historical-resampling forecast and does not establish predictive momentum excess returns.

{summary.to_markdown(index=False, floatfmt='.6f')}

The outperformance frequency is the proportion of scenarios outperforming Fund X under the specified historical sample and simulation assumptions. Execution failures remain explicitly counted, and summary statistics identify any incomplete scenario population.

{pairs.to_markdown(index=False, floatfmt='.6f')}

The actual result's percentile uses the same strategy's simulated net-liquidation-return distribution. The simulated market paths start at each asset's last pre-cutoff adjusted close and use the same execution and accounting engine as the historical replay. This preserves an asset-specific unit scale for rounding without using evaluation prices.

## Published baseline reconciliation

{reconciliation.to_markdown(index=False, floatfmt='.9f')}

The published baseline charges 2% annual borrow on initial short exposure over trading intervals divided by 252. The standardized ledger charges 2% annual borrow on the preceding day's outstanding short market value over elapsed calendar days divided by 365. Initial fees use original capital, and exit fees use actual ending notional. Both retain zero cash interest. The gross P0 path and the daily-rebalanced Fund X definition reproduce the saved baseline.

## Benchmark and financing

Fund X is a daily-rebalanced proxy benchmark with 20% `^SPGSCI`, 50% `URTH`, and 30% `BNDW`. Its index and ETF returns are compounded daily. B0 has no assumed portfolio transaction fees: it is a reference index calculation. `^SPGSCI` is an index observation. Benchmark turnover and costs of zero are placeholders for the reference calculation; an executable implementation requires instruments, spreads, and fees.

The cash account includes signed short proceeds. Current short market value is restricted as collateral; available cash is cash minus restricted collateral. The engine rejects unavailable financing and invalid prices. Borrow availability, initial margin in excess of 100% short market value, market impact, taxes, and execution capacity at $500 million remain unverified. The 2% borrow rate and 10-basis-point trading fee are illustrative assumptions.

## Data and research limits

''' + '\n\n'.join('- '+warning for warning in warnings) + '''

The evaluation period had already been explored during research. These are historical diagnostic comparisons. Code-level cutoff enforcement preserves computational causality; it cannot remove prior researcher knowledge. The original analysis, forecasts, notebooks, and outputs are retained separately.
'''
    (out/'report.md').write_text(text, encoding='utf-8')


def build_manifest(config, policy_path, data_paths, extra):
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    dependencies = {}
    for name in ['numpy', 'pandas', 'scikit-learn', 'exchange-calendars', 'matplotlib', 'nbformat', 'nbclient']:
        dependencies[name] = importlib.metadata.version(name)
    return {'code_revision': revision, 'code_revision_note': 'Parent revision plus source hashes identify this working-tree implementation.',
            'configuration': config, 'policy_sha256': sha256(policy_path),
            'data': {str(p): sha256(p) for p in data_paths},
            'source_sha256': {str(p): sha256(p) for p in sorted(Path('rebalancing').glob('*.py'))} | {'run_rebalancing.py': sha256('run_rebalancing.py')},
            'dependencies': dependencies, 'random_seed': config['seed'],
            'execution': 'idealized adjusted-close fills; preceding close monthly sizing; fractional synthetic units',
            **extra}
