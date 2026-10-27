"""Run training-only preparation, freeze, paired scenarios, then historical replay."""
import argparse
import json
from pathlib import Path
import os
import pandas as pd
from rebalancing.data_access import load_config, load_training, load_evaluation, resolve_path
from rebalancing.policies import freeze_policy, verify_freeze
from rebalancing.risk_model import diagnostics
from rebalancing.simulation import simulate, paired_comparisons
from rebalancing.evaluation import evaluate, reconcile_baseline
from rebalancing.reporting import build_manifest, write_report

ROOT = Path(__file__).resolve().parent


def main(config_path=None):
    os.chdir(ROOT)
    config = load_config(config_path)
    # Aliases keep the public configuration expressed in bps and annual rates.
    config['capital'] = config.get('capital', 500e6)
    config['trading_cost'] = config['transaction_cost_bps']/10000
    config['borrow_rate'] = config['annual_borrow_rate']
    out = ROOT/'aligned_method/rebalancing'
    out.mkdir(parents=True, exist_ok=True)
    training = load_training(config)
    policy = freeze_policy(config, training)
    (out/'frozen_policy.json').write_text(json.dumps(policy, indent=2), encoding='utf-8')
    diagnostics(training, pd.Series(policy['weights']), policy['sectors']).to_csv(out/'risk_diagnostics.csv', index=False)
    verify_freeze(policy)
    print('Frozen policy before simulation and evaluation price access', flush=True)
    if not policy['joint_simulation_ready']:
        raise ValueError(policy['simulation_block_reason'])
    samples, summary, simulation_metadata = simulate(training, policy, config)
    samples.to_csv(out/'simulation_samples.csv', index=False)
    pairs = paired_comparisons(samples)
    verify_freeze(policy)
    prices = load_evaluation(config)
    evaluation = evaluate(prices, policy, config, samples)
    reconciliation = reconcile_baseline(prices, policy, config, evaluation)
    data_paths = [resolve_path(config, key) for key in ['training_path', 'evaluation_path', 'weights_path', 'sectors_path']]
    data_paths += [Path('data/rebalancing_benchmark_training.csv'), Path('data/rebalancing_training_provenance.json')]
    data_paths = [p for p in data_paths if p.exists()]
    manifest = build_manifest(config, out/'frozen_policy.json', data_paths, simulation_metadata)
    warnings = [
        'The original stock training data is derived from synthetic_prices.csv. Its provenance, survivorship coverage, and corporate-action conventions remain independently unverified.',
        'The cached evaluation prices were downloaded by the original analysis with yfinance auto_adjust=True. Stock, URTH, and BNDW levels therefore represent dividend/split-adjusted return proxies. Exact cached corporate-action adjustments have not been independently reconciled. https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html',
        '^SPGSCI is the S&P GSCI price/spot index series; the separate total-return series is ^SPGSCITR. It omits the total-return variant collateral yield. Fund X mixes this price index with ETF adjusted-return proxies and is not an independently verified tradable fund. https://finance.yahoo.com/quote/%5ESPGSCI/ ; https://finance.yahoo.com/quote/%5ESPGSCITR/',
        'Opening fills, action-level dividends, split events, halts, delistings, and borrow availability are unavailable in the cached evaluation panel. Adjusted-close synthetic-unit accounting includes short dividend effects through signed adjusted returns; separate dividend cash flows are not added.',
        'The initial allocation uses fractional synthetic units; subsequent monthly quantity changes are rounded to the nearest whole synthetic unit. These adjusted units cannot be interpreted as exchange-executable shares.',
        'Missing or nonpositive prices cause a hard failure. No backfilling or assumed missing-price fills occur. Insufficient collateral cash or nonpositive NAV rejects a scenario and is explicitly counted.',
        'Benchmark pre-cutoff adjusted prices were fetched separately from Yahoo Finance and are archived with hashes. The joint panel combines this source with the original stock training panel. Source revisions and convention differences can affect the result.',
        'The risk budget is unconfigured by default. P2/P3 remain visible as unconfigured relaxed-exposure variants. The pre-cutoff diagnostics support choosing a budget in a separate prospective research decision.',
        'The 2026 evaluation period has been explored before this implementation. This is a historical diagnostic comparison, with illustrative costs and financing constraints.'
    ]
    write_report(out, config, policy, evaluation, summary, pairs, reconciliation, warnings, manifest)
    print(evaluation['actual_metrics'].to_string(index=False), flush=True)
    print(f'Completed research artifacts: {out}', flush=True)
    return evaluation


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=None)
    args = parser.parse_args()
    main(args.config)
