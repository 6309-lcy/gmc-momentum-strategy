"""Independent risk-driven hedge research; original stock ledger stays untouched."""
from pathlib import Path
import hashlib
import json
import subprocess
import os
import numpy as np
import pandas as pd
from hedging.data_access import load_joint
from hedging.model import fit_model, filter_states
from hedging.accounting import run_overlay
from rebalancing.accounting import run_path
from rebalancing.simulation import joint_indices, path_metrics, benchmark_nav

ROOT=Path(__file__).resolve().parent
MODES={'H0':'reserve','H1':'static','H2':'dynamic'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate_path(prices,weights,model,config,record=False):
    stock=run_path(prices[weights.index],weights,[],capital=config['stock_capital'],
                   trading_cost=config['trading_cost'],borrow_rate=config['stock_borrow_rate'],record=record)
    signals=filter_states(prices,model,weights)
    results={}
    total=config['stock_capital']+config['overlay_capital']
    benchmark=benchmark_nav(prices,total)
    for name,mode in MODES.items():
        overlay=run_overlay(prices,signals,model,capital=config['overlay_capital'],
                            stock_capital=config['stock_capital'],trading_cost=config['trading_cost'],
                            cash_buffer=config['cash_buffer'],mode=mode,on_insufficient_cash='reject')
        nav=stock['nav'].nav+overlay['nav'].nav
        liquidated=nav.copy()
        liquidated.iloc[-1]=stock['nav'].liquidation_nav.iloc[-1]+overlay['nav'].liquidation_nav.iloc[-1]
        stats=path_metrics(liquidated,total,benchmark)
        stats.update(rejected_orders=len(overlay['rejections']),overlay_return=overlay['nav'].liquidation_nav.iloc[-1]/config['overlay_capital']-1,
                     stock_net_return=stock['nav'].liquidation_nav.iloc[-1]/config['stock_capital']-1,
                     overlay_transaction_cost=overlay['nav'].transaction_cost.sum(),
                     overlay_terminal_cost=overlay['nav'].nav.iloc[-1]-overlay['nav'].liquidation_nav.iloc[-1],
                     hedge_active_fraction=float((overlay['nav'].sh_value>0).mean()))
        results[name]={'metrics':stats,'combined_nav':nav,'performance_nav':liquidated,'overlay':overlay}
    return results,stock,signals


def main():
    os.chdir(ROOT)
    config=json.loads(Path('hedging/config.json').read_text())
    out=Path('aligned_method/hedging'); out.mkdir(parents=True,exist_ok=True)
    weights=pd.read_csv('aligned_method/validated_strategy/frozen_weights.csv',index_col=0).weight
    training=load_joint('training')
    model=fit_model(training,weights,decay=config['decay'])
    frozen={'config':config,'model':model,'weights':weights.to_dict(),
            'training_sha256':digest('data/hedging/training_instruments.csv'),
            'stock_weights_sha256':digest('aligned_method/validated_strategy/frozen_weights.csv')}
    (out/'frozen_policy.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    frozen_hash=digest(out/'frozen_policy.json')
    import exchange_calendars as xcals
    dates=xcals.get_calendar('XNYS').sessions_in_range(config['evaluation_start'],config['evaluation_end']).tz_localize(None)
    returns=training.pct_change(fill_method=None).iloc[1:]
    indices=joint_indices(len(returns),len(dates)-1,config['n_paths'],config['block_length'],config['seed'])
    rows=[]; examples=[]
    for path,sampled in enumerate(indices):
        p=pd.DataFrame(np.vstack([np.ones(training.shape[1]),np.cumprod(1+returns.values[sampled],axis=0)])*
                       training.iloc[-1].values,index=dates,columns=training.columns)
        result,_,signals=evaluate_path(p,weights,model,config)
        for name,value in result.items():
            rows.append({'path':path,'strategy':name,**value['metrics']})
            if path<20:
                for date,nav in value['combined_nav'].items():
                    examples.append({'path':path,'date':date,'strategy':name,'nav':nav,
                                     'stress':int(signals.loc[date,'hedge_active'])})
        if (path+1)%1000==0: print(f'Completed {path+1}/{config["n_paths"]} hedge scenarios',flush=True)
    samples=pd.DataFrame(rows); samples.to_csv(out/'simulation_samples.csv',index=False)
    summary=[]
    for name,g in samples.groupby('strategy'):
        r=g.net_return; q=r.quantile(.05)
        summary.append({'strategy':name,'mean_net_return':r.mean(),'median_net_return':r.median(),
                        'p05':q,'p95':r.quantile(.95),'loss_frequency':(r<0).mean(),
                        'worst5_mean':r[r<=q].mean(),'mean_max_drawdown':g.max_drawdown.mean(),
                        'mean_overlay_cost':g.overlay_transaction_cost.mean(),'mean_rejected_orders':g.rejected_orders.mean(),'mean_hedge_fraction':g.hedge_active_fraction.mean()})
    summary=pd.DataFrame(summary); summary.to_csv(out/'simulation_summary.csv',index=False)
    pairs=[]; wide=samples.pivot(index='path',columns='strategy',values='net_return')
    for name in ['H1','H2']:
        delta=wide[name]-wide.H0
        pairs.append({'comparison':name+' minus H0','mean_difference':delta.mean(),'p05':delta.quantile(.05),
                      'p95':delta.quantile(.95),'positive_frequency':(delta>0).mean()})
    pd.DataFrame(pairs).to_csv(out/'paired_comparisons.csv',index=False)
    pd.DataFrame(examples).to_csv(out/'simulation_examples.csv',index=False)
    assert digest(out/'frozen_policy.json')==frozen_hash
    prices=load_joint('evaluation')
    result,stock,signals=evaluate_path(prices,weights,model,config,record=True)
    actual=[]; navs=[]; overlays=[]; trades=[]; rejections=[]
    for name,value in result.items():
        r=value['metrics']; distribution=samples.loc[samples.strategy==name,'net_return']
        actual.append({'strategy':name,**r,'simulation_percentile':(distribution<=r['net_return']).mean()*100})
        navs.append(pd.DataFrame({'date':dates,'strategy':name,'combined_nav':value['combined_nav'].values,'performance_nav':value['performance_nav'].values,
                                  'stock_nav':stock['nav'].nav.values,'overlay_nav':value['overlay']['nav'].nav.values}))
        overlays.append(value['overlay']['nav'].rename_axis('date').reset_index().assign(strategy=name))
        trades.append(value['overlay']['trades'].assign(strategy=name))
        rejections.append(value['overlay']['rejections'].assign(strategy=name))
    actual=pd.DataFrame(actual); actual.to_csv(out/'actual_metrics.csv',index=False)
    pd.concat(navs).to_csv(out/'daily_nav.csv',index=False)
    pd.concat(overlays).to_csv(out/'overlay_accounts.csv',index=False)
    pd.concat(trades).to_csv(out/'trades.csv',index=False)
    pd.concat(rejections).to_csv(out/'rejections.csv',index=False)
    signals.to_csv(out/'signals.csv')
    stock['nav'].to_csv(out/'stock_nav.csv')
    from hedging.reporting import write_report
    write_report(out,config,model,actual,summary,pd.DataFrame(pairs))
    files=list(Path('hedging').glob('*.py'))+[Path('run_hedging.py')]
    data=[Path('data/hedging/training_instruments.csv'),Path('data/hedging/evaluation_instruments.csv'),
          Path('data/rebalancing_training.csv'),Path('aligned_method/validated_strategy/diagnostic_prices.csv')]
    manifest={'code_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'source_sha256':{str(p):digest(p) for p in files},'data_sha256':{str(p):digest(p) for p in data},
              'frozen_policy_sha256':frozen_hash,'scenario_indices_sha256':hashlib.sha256(indices.tobytes()).hexdigest(),
              'config':config,'data_note':'Yahoo auto_adjust=True snapshots retrieved 2026-10-27; original stock provenance remains unverified'}
    (out/'run_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(actual.to_string(index=False),flush=True)
    return actual


if __name__=='__main__': main()
