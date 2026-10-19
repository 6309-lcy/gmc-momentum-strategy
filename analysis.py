"""Reproduce chronological selection, forecasts, and diagnostic evaluations."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf
from IPython.display import display
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'aligned_method/validated_strategy'
OUT.mkdir(parents=True,exist_ok=True)
AUM=500e6
CUTOFF=pd.Timestamp('2026-04-28')
raw=pd.concat(pd.read_csv(path,index_col=0,parse_dates=True) for path in sorted((ROOT/'data').glob('training_prices_*.csv'))).loc[:CUTOFF]
stock_allowlist = set("AAPL ABT ADBE AGCO AMD AMGN AMZN ARRY AVGO AXON AXP BA BAC BBVA BCS BE BHC BIIB BK BKR BLK BMRN BMY BP C CACI CAT CBOE CME CNQ COP CRM CRWD CSIQ CVX DB DE DHR DVN DXCM EMR ENPH EOG EQNR ERIC FANG FIVN FOLD FSLR FTNT GD GE GILD GOOGL GS HAL HII HON HSBC ICE ILMN ING INTC ISRG ITW JNJ JPM KTOS LDOS LLY LMT LYFT MA MCO META MMM MPC MRNA MS MSFT MU NET NOC NOK NVDA ORCL PANW PFE PINS PLTR PLUG PODD PRGO PSX QCOM REGN ROK RTX RUN RXRX SAIC SAN SAP SEDG SHEL SLB SPGI STT TMO TSLA TTE TXN UBER UBS UNH V VLO VRTX WAL WDC WFC XOM ZS".split())
SECTOR = {}
for t in ['AAPL','MSFT','GOOGL','AMZN','META','NVDA','TSLA','ORCL','CRM','ADBE',
          'PLTR','CRWD','PANW','ZS','FTNT','NET','SAIC','LDOS','AVGO','TXN',
          'ERIC','NOK','SAP','UBER','LYFT','QCOM','INTC','AMD','MU','WDC','PINS','FIVN']:
    SECTOR[t] = 'Tech'
for t in ['LLY','UNH','JNJ','ABT','TMO','DHR','ISRG','VRTX','REGN','BMY',
          'AMGN','GILD','ILMN','DXCM','PODD','MRNA','TDOC','PFE','BMRN',
          'BIIB','PRGO','BHC','FOLD','RXRX']:
    SECTOR[t] = 'Healthcare'
for t in ['GS','JPM','MS','BAC','BLK','V','MA','AXP','SPGI','ICE','CME','CBOE',
          'MCO','BK','STT','DB','UBS','BCS','SAN','BBVA','ING','HSBC','C','WFC','WAL']:
    SECTOR[t] = 'Finance'
for t in ['LMT','RTX','NOC','GD','HII','KTOS','AXON','CACI','HON',
          'GE','EMR','ITW','ROK','AGCO','BA','MMM','CAT','DE']:
    SECTOR[t] = 'Industrials'
for t in ['XOM','CVX','COP','EOG','MPC','PSX','VLO','DVN','FANG',
          'SLB','HAL','BKR','EQNR','ENPH','FSLR','SEDG','RUN',
          'CSIQ','BE','PLUG','BP','TTE','SHEL','CNQ']:
    SECTOR[t] = 'Energy'


sector_map={t:SECTOR.get(t,'Other') for t in stock_allowlist}
# Only use the Phase 2 signal at dates after it was observed.
a=raw.loc['2022-05-24':'2022-08-24']
analogy=a.ffill().iloc[-1]/a.ffill().iloc[0]-1
RULES=['momentum','momentum_stability','momentum_stability_analogy']
LAMBDAS=[2.,10.,20.]


def rank_score(x):
    return x.rank(pct=True)*2-1

def allocate(train,rule,lam):
    p=train[[t for t in train if t in stock_allowlist]]
    r=p.pct_change(fill_method=None).iloc[1:]
    valid=(r.notna().mean()>=.98)&(r.abs().max()<=.40)&(p.min()>0)
    if train.index.max()>=pd.Timestamp('2026-04-27') and 'FOLD' in valid.index:
        valid.loc['FOLD']=False  # Acquired and delisted before the May entry.
    p=p.loc[:,valid].ffill();r=r.loc[:,valid].fillna(0)
    assert len(p)>=450
    m12=p.iloc[-22]/p.iloc[-253]-1
    m6=p.iloc[-22]/p.iloc[-127]-1
    m3=p.iloc[-1]/p.iloc[-64]-1
    vol=r.iloc[-126:].std()*np.sqrt(252)
    downside=np.sqrt((r.iloc[-126:].clip(upper=0)**2).mean())*np.sqrt(252)
    groups=pd.Series({t:sector_map[t] for t in p})
    relative=m6-m6.groupby(groups).transform('median')
    momentum=.35*rank_score(m12)+.30*rank_score(m6)+.15*rank_score(m3)+.20*rank_score(relative)
    stability=.5*rank_score(-vol)+.5*rank_score(-downside)
    score=momentum if rule=='momentum' else .8*momentum+.2*stability
    if rule.endswith('analogy'):
        assert p.index.max()>=pd.Timestamp('2022-08-24')
        score=.9*score+.1*rank_score(analogy.reindex(p.columns).fillna(0))
    score=score.dropna()
    ordered=score.sort_values(ascending=False)
    counts={};longs=[];shorts=[]
    for t in ordered.index:
        g=sector_map[t]
        if counts.get(g,0)<4:
            longs.append(t);counts[g]=counts.get(g,0)+1
        if len(longs)==8:break
    for t in ordered.index[::-1]:
        g=sector_map[t]
        if t not in longs and counts.get(g,0)<4:
            shorts.append(t);counts[g]=counts.get(g,0)+1
        if len(shorts)==4:break
    assert len(longs)==8 and len(shorts)==4
    names=longs+shorts;sign=np.r_[np.ones(8),-np.ones(4)]
    rr=r[names];lw=LedoitWolf().fit(rr.values);cov=lw.covariance_*252
    mu=.06+.08*score.reindex(names)
    scov=cov*np.outer(sign,sign)
    cons=[{'type':'eq','fun':lambda z:z[:8].sum()-.8},{'type':'eq','fun':lambda z:z[8:].sum()-.2}]
    for group in set(sector_map[t] for t in names):
        mask=np.array([sector_map[t]==group for t in names],float)
        cons.append({'type':'ineq','fun':lambda z,m=mask:.45-z@m})
    # Four 5% shorts exhaust the 20% short budget: fix them explicitly.
    short_fixed=np.full(4,.05)
    long_cons=[{'type':'eq','fun':lambda z:z.sum()-.8}]
    for group in set(sector_map[t] for t in names):
        mask=np.array([sector_map[t]==group for t in names],float)
        long_cons.append({'type':'ineq','fun':lambda z,m=mask:.45-z@m[:8]-short_fixed@m[8:]})
    def obj(z):
        x=np.r_[z,short_fixed]
        return -(sign*x)@mu.values+lam*x@scov@x+.01*(x@x)
    def grad(z):
        x=np.r_[z,short_fixed]
        return (-sign*mu.values+2*lam*scov@x+.02*x)[:8]
    f=minimize(obj,np.full(8,.1),jac=grad,method='SLSQP',bounds=[(.05,.15)]*8,
        constraints=long_cons,options={'maxiter':500,'ftol':1e-10})
    assert f.success,f.message
    f.x=np.r_[f.x,short_fixed]
    w=pd.Series(sign*f.x,index=names)
    assert np.isclose(w.abs().sum(),1) and w.abs().min()>=.05-1e-7
    for group in set(sector_map[t] for t in names):assert w[[t for t in names if sector_map[t]==group]].abs().sum()<=.450001
    return w,mu,pd.DataFrame(cov,index=names,columns=names),score

def block_nav(w,test,costs=True):
    q=test[w.index]
    assert not q.isna().any().any()
    wealth=1-w.sum()+(q/q.iloc[0])@w
    if costs:
        # Cash-paid execution costs and daily borrow charged against initial equity.
        wealth=wealth-.001*w.abs().sum()-.02*(-w.clip(upper=0).sum())*np.arange(len(q))/252
        wealth.iloc[-1]-=.001*(w.abs()*(q.iloc[-1]/q.iloc[0])).sum()
    return wealth

def metrics(nav):
    rr=nav.pct_change().dropna()
    return {'Return':nav.iloc[-1]/nav.iloc[0]-1,'Annual volatility':rr.std()*np.sqrt(252),
        'Max drawdown':(nav/nav.cummax()-1).min(),'Arithmetic Sharpe':(rr.mean()*252-.045)/(rr.std()*np.sqrt(252))}

# Nonoverlapping validation return blocks; shared boundary prices are intentional.
all_dates=raw.index
start=int(all_dates.searchsorted(pd.Timestamp('2023-01-03')))
folds=[]
for i in range(start,len(all_dates)-63,63):
    decision=all_dates[i]
    train=raw.loc[(raw.index>decision-pd.DateOffset(years=2))&(raw.index<=decision)]
    test=raw.iloc[i:i+64]
    assert train.index.max()==test.index.min() and test.index.max()<=CUTOFF
    folds.append((train,test))
results=[];detail=[];paths={}
for rule in RULES:
    for lam in LAMBDAS:
        daily=[]
        for k,(train,test) in enumerate(folds):
            w,_,_,_=allocate(train,rule,lam)
            wealth=block_nav(w,test)
            # Entry/exit costs enter the first and last return respectively.
            growth=np.r_[1.,wealth.values[1:]]
            rr=pd.Series(growth[1:]/growth[:-1]-1,index=test.index[1:])
            daily.append(rr)
            detail.append({'Rule':rule,'Risk penalty':lam,'Fold':k+1,'Train start':str(train.index[0].date()),
                'Train end':str(train.index[-1].date()),'Test end':str(test.index[-1].date()),'Net block return':wealth.iloc[-1]-1})
        rr=pd.concat(daily);v=(1+rr).cumprod();v=pd.concat([pd.Series([1.],index=[folds[0][1].index[0]]),v])
        stats=metrics(v)
        # Penalise variance; drawdown acts as tie-break information rather than tuning.
        score=rr.mean()*252-2*rr.var()*252
        results.append({'Rule':rule,'Risk penalty':lam,**stats,'Selection score':score,'Validation returns':len(rr)})
        paths[(rule,lam)]=v
        print('Finished',rule,lam,flush=True)
leaderboard=pd.DataFrame(results).sort_values('Selection score',ascending=False)
leaderboard.to_csv(OUT/'validation_leaderboard.csv',index=False)
pd.DataFrame(detail).to_csv(OUT/'validation_folds.csv',index=False)
display(leaderboard)
chosen=leaderboard.iloc[0];rule=chosen.Rule;lam=float(chosen['Risk penalty'])
train=raw.loc['2024-04-29':'2026-04-28']
w,mu,cov,score=allocate(train,rule,lam)
manifest={'cutoff':str(CUTOFF.date()),'training_start':str(train.index[0].date()),'rule':rule,'risk_penalty':lam,
    'gross_budget':AUM,'long_fraction':.8,'short_fraction':.2,'min_position':.05,'max_position':.15,'sector_gross_cap':.45,
    'validation_folds':len(folds),'note':'Historical validation used for model selection; later 2026 outcome is diagnostic'}
w.rename('weight').to_csv(OUT/'frozen_weights.csv')
manifest['weights_sha256']=hashlib.sha256((OUT/'frozen_weights.csv').read_bytes()).hexdigest()
(OUT/'frozen_strategy.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('FROZEN STRATEGY:',manifest)
portfolio=pd.DataFrame({'Weight':w,'Sector':[sector_map[t] for t in w.index],'Position ($m)':w*500,'Expected annual return':mu})
portfolio.to_csv(OUT/'initial_portfolio.csv');display(portfolio)
fig,axes=plt.subplots(1,2,figsize=(16,7))
for (name,l),v in paths.items():
    if l==lam:v.plot(ax=axes[0],label=name)
axes[0].set_title('Chronological validation | net of assumed costs');axes[0].legend(fontsize=8)
s=w.sort_values()*100;axes[1].barh(s.index,s,color=['#b54747' if x<0 else '#227c9d' for x in s]);axes[1].axvline(0,color='grey')
axes[1].set_xlabel('Initial weight (%)');axes[1].set_title('Selected final portfolio')
fig.tight_layout();fig.savefig(OUT/'validation_and_weights.png',dpi=160,bbox_inches='tight');plt.show()


sensitivity=[]
for penalty in [max(lam/2,1),lam,lam*2]:
    sw,sm,sc,_=allocate(train,rule,penalty)
    sensitivity.append({'Risk penalty':penalty,'Expected annual return':sw@sm,'Annual model volatility':np.sqrt(sw@sc@sw),
        'Weight difference L1':(sw-w).abs().sum()})
pd.DataFrame(sensitivity).to_csv(OUT/'risk_sensitivity.csv',index=False)
display(pd.DataFrame(sensitivity))
rng=np.random.default_rng(2026)
shock=mu.values/252+rng.standard_normal((10000,63,len(w)))@np.linalg.cholesky(cov.values/252+np.eye(len(w))*1e-12).T
mc=100*((1-w.sum())+np.cumprod(1+shock,axis=1)@w.values)
mc=np.c_[np.full(10000,100.),mc]
terminal=mc[:,-1]/100-1
mc_summary=pd.Series({'Mean return':terminal.mean(),'Median return':np.median(terminal),'5th percentile':np.percentile(terminal,5),
    '95th percentile':np.percentile(terminal,95),'Probability positive':(terminal>0).mean()})
mc_summary.to_csv(OUT/'mc_summary.csv');print(mc_summary.to_string())


import yfinance as yf
assert hashlib.sha256((OUT/'frozen_weights.csv').read_bytes()).hexdigest()==manifest['weights_sha256']
cache=OUT/'diagnostic_prices.csv'
if cache.exists():px=pd.read_csv(cache,index_col=0,parse_dates=True)
else:
    tickers=list(w.index)+['^SPGSCI','URTH','BNDW']
    data=yf.download(tickers,start='2026-05-01',end='2026-08-05',auto_adjust=True,progress=False)
    px=data['Close'].reindex(columns=tickers).iloc[:64]
    assert len(px)==64 and not px.isna().any().any()
    px.to_csv(cache)
assert px.index[0]==pd.Timestamp('2026-05-01') and px.index[-1]==pd.Timestamp('2026-08-03')
gross=block_nav(w,px,costs=False)*100
net=block_nav(w,px,costs=True)*100
fxd=(px[['^SPGSCI','URTH','BNDW']].pct_change(fill_method=None)*pd.Series({'^SPGSCI':.2,'URTH':.5,'BNDW':.3})).sum(axis=1)
nav=pd.DataFrame({'Portfolio gross':gross,'Portfolio assumed-cost net':net,'Fund X proxy':100*(1+fxd).cumprod()})
# Net return uses starting equity before entry costs.
metric_paths=nav.copy()
metric_paths.iloc[0]=100.0
realised=pd.DataFrame({c:metrics(metric_paths[c]) for c in nav}).T
realised['Return']=nav.iloc[-1].values/100-1
realised['P&L ($m)']=realised.Return*500
realised.to_csv(OUT/'diagnostic_scorecard.csv');nav.to_csv(OUT/'diagnostic_nav.csv');display(realised)
actual=gross.iloc[-1]/100-1
print('Realised percentile in Monte Carlo:',100*(terminal<=actual).mean())
q=np.percentile(mc,[5,25,50,75,95],axis=0)
fig,axes=plt.subplots(1,2,figsize=(15,6))
axes[0].fill_between(px.index,q[0],q[4],alpha=.15,label='MC 5–95%')
axes[0].fill_between(px.index,q[1],q[3],alpha=.25,label='MC 25–75%')
axes[0].plot(px.index,q[2],ls='--',label='MC median')
nav.plot(ax=axes[0]);axes[0].legend(fontsize=8);axes[0].set_ylabel('NAV')
axes[1].hist(terminal*100,bins=60,alpha=.6)
axes[1].axvline(actual*100,color='#b54747',label=f'Diagnostic actual {actual:+.2%}');axes[1].legend()
axes[1].set_xlabel('63-return outcome (%)')
fig.tight_layout();fig.savefig(OUT/'forecast_vs_diagnostic.png',dpi=160,bbox_inches='tight');plt.show()


h=pd.read_csv(OUT/'initial_portfolio.csv',index_col=0)
cov=cov.values if isinstance(cov,pd.DataFrame) else cov
# Check sensitivity to forecast assumptions; weights are never retuned.
rows=[]
for label,mean_scale,vol_scale in [('Base',1.,1.),('Half expected returns',.5,1.),('50% higher volatility',1.,1.5),('Both stressed',.5,1.5)]:
    rng=np.random.default_rng(2026)
    shocks=mu.values/252*mean_scale+rng.standard_normal((10000,63,len(w)))@np.linalg.cholesky(cov/252+np.eye(len(w))*1e-12).T*vol_scale
    growth=np.cumprod(1+shocks,axis=1)
    end=(1-w.sum())+growth[:,-1,:]@w.values
    costs=.001*w.abs().sum()+.001*(growth[:,-1,:]@w.abs().values)+.02*(-w.clip(upper=0).sum())*63/252
    net=end-costs-1
    gross=end-1
    rows.append({'Scenario':label,'Gross mean':gross.mean(),'Net mean':net.mean(),'Net median':np.median(net),
        'Net 5th percentile':np.percentile(net,5),'Net 95th percentile':np.percentile(net,95),'Net probability positive':(net>0).mean()})
stress=pd.DataFrame(rows).set_index('Scenario');stress.to_csv(OUT/'forecast_stress_and_costs.csv');display(stress)
asset_returns=px[w.index].iloc[-1]/px[w.index].iloc[0]-1
attribution=pd.DataFrame({'Weight':w,'Sector':h.Sector,'Asset return':asset_returns,'Contribution (pp)':w*asset_returns*100,'P&L ($m)':w*asset_returns*500}).sort_values('P&L ($m)')
attribution.to_csv(OUT/'diagnostic_attribution.csv')
actual=pd.read_csv(OUT/'diagnostic_scorecard.csv',index_col=0)
assert np.isclose(attribution['P&L ($m)'].sum(),actual.loc['Portfolio gross','P&L ($m)'])
assert np.isclose(w.abs().sum(),1) and w.abs().min()>=.05-1e-7 and w.abs().max()<=.15+1e-7
assert np.isclose(w.clip(lower=0).sum(),.8) and np.isclose(-w.clip(upper=0).sum(),.2)
assert (h.groupby('Sector').Weight.apply(lambda z:z.abs().sum())<=.45+1e-6).all()
display(attribution)
fig,axes=plt.subplots(1,2,figsize=(16,7))
s=attribution['P&L ($m)'];axes[0].barh(s.index,s,color=['#b54747' if v<0 else '#227c9d' for v in s]);axes[0].axvline(0,color='grey');axes[0].set_xlabel('Diagnostic holding P&L ($m)')
d=np.sqrt(np.diag(cov));corr=cov/np.outer(d,d)
im=axes[1].imshow(corr,vmin=-1,vmax=1,cmap='RdBu_r');axes[1].set_xticks(range(len(w)),w.index,rotation=90);axes[1].set_yticks(range(len(w)),w.index);axes[1].set_title('Selected holdings: Ledoit–Wolf correlation');fig.colorbar(im,ax=axes[1],shrink=.8)
fig.tight_layout();fig.savefig(OUT/'attribution_and_correlation.png',dpi=160,bbox_inches='tight');plt.show()
print('Verified minimum sizes, gross budget, sector cap and attribution reconciliation')


cache=OUT/'prices_to_9_oct.csv'
if cache.exists():extended_prices=pd.read_csv(cache,index_col=0,parse_dates=True)
else:
    tickers=list(w.index)+['^SPGSCI','URTH','BNDW']
    data=yf.download(tickers,start='2026-05-01',end='2026-10-10',auto_adjust=True,progress=False)
    extended_prices=data['Close'].reindex(columns=tickers)
    assert not extended_prices.isna().any().any()
    extended_prices.to_csv(cache)
assert extended_prices.index[0]==pd.Timestamp('2026-05-01') and extended_prices.index[-1]==pd.Timestamp('2026-10-09')
growth=extended_prices[w.index]/extended_prices[w.index].iloc[0]
gross=100*((1-w.sum())+growth@w)
entry=.001*w.abs().sum()
borrow=.02*(-w.clip(upper=0).sum())*np.arange(len(gross))/252
net=gross-100*(entry+borrow)
net.iloc[-1]-=100*.001*(w.abs()*growth.iloc[-1]).sum()
fxr=(extended_prices[['^SPGSCI','URTH','BNDW']].pct_change(fill_method=None)*pd.Series({'^SPGSCI':.2,'URTH':.5,'BNDW':.3})).sum(axis=1)
extended_nav=pd.DataFrame({'Portfolio gross':gross,'Portfolio assumed-cost net':net,'Fund X proxy':100*(1+fxr).cumprod()})
rows={}
for label in extended_nav:
    q=extended_nav[label].copy();q.iloc[0]=100
    daily=q.pct_change().dropna()
    ret=extended_nav[label].iloc[-1]/100-1
    rows[label]={'Return':ret,'P&L ($m)':ret*500,'Annual volatility':daily.std()*np.sqrt(252),
        'Max drawdown':(q/q.cummax()-1).min(),'Return intervals':len(q)-1}
extended_score=pd.DataFrame(rows).T
extended_nav.to_csv(OUT/'nav_to_9_oct.csv');extended_score.to_csv(OUT/'scorecard_to_9_oct.csv')
print(extended_score.to_string())
short_path=pd.read_csv(OUT/'diagnostic_nav.csv',index_col=0,parse_dates=True)
assert np.allclose(extended_nav.loc[short_path.index,'Portfolio gross'],short_path['Portfolio gross'])
attribution=pd.DataFrame({'Weight':w,'Asset return':growth.iloc[-1]-1,'P&L ($m)':w*(growth.iloc[-1]-1)*500}).sort_values('P&L ($m)')
assert np.isclose(attribution['P&L ($m)'].sum(),extended_score.loc['Portfolio gross','P&L ($m)'])
attribution.to_csv(OUT/'attribution_to_9_oct.csv');display(attribution)
fig,axes=plt.subplots(3,1,figsize=(14,12),sharex=True)
extended_nav.plot(ax=axes[0],title='Frozen validated strategy | 1 May–9 October 2026')
axes[0].set_ylabel('NAV (100 at entry)')
((extended_nav/100-1)*500).plot(ax=axes[1]);axes[1].set_ylabel('P&L ($ million)')
((extended_nav/extended_nav.cummax()-1)*100).plot(ax=axes[2]);axes[2].set_ylabel('Drawdown (%)')
for ax in axes:
    ax.axvline(pd.Timestamp('2026-08-03'),color='grey',ls=':',label='63-return checkpoint')
    ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.tight_layout();fig.savefig(OUT/'performance_to_9_oct.png',dpi=160,bbox_inches='tight');plt.show()
fig,ax=plt.subplots(figsize=(12,7))
s=attribution['P&L ($m)'];ax.barh(s.index,s,color=['#b54747' if x<0 else '#227c9d' for x in s]);ax.axvline(0,color='grey')
ax.set_xlabel('P&L ($ million)');ax.set_title('Holding contributions through 9 October')
fig.tight_layout();fig.savefig(OUT/'attribution_to_9_oct.png',dpi=160,bbox_inches='tight');plt.show()

