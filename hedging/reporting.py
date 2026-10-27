"""Separate hedge figures and research report."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd


def write_report(out,config,model,actual,summary,pairs):
    out=Path(out); figures=out/'figures'; figures.mkdir(exist_ok=True)
    nav=pd.read_csv(out/'daily_nav.csv',parse_dates=['date'])
    signals=pd.read_csv(out/'signals.csv',index_col=0,parse_dates=True)
    fig,axes=plt.subplots(3,1,figsize=(12,11),sharex=True)
    for name,g in nav.groupby('strategy'):
        axes[0].plot(g.date,g.performance_nav/7e6,label=name)
        v=pd.Series(g.performance_nav.values,index=g.date)
        peak=v.cummax().clip(lower=config['stock_capital']+config['overlay_capital'])
        axes[1].plot(g.date,v/peak-1,label=name)
    axes[0].set(ylabel='Combined NAV (700m = 100)',title='Independent 200m overlay | historical close-price diagnostic')
    axes[0].legend();axes[1].set(ylabel='Drawdown')
    axes[2].plot(signals.index,signals.volatility,label='Stock EWMA volatility')
    axes[2].fill_between(signals.index,0,signals.volatility.max(),where=signals.hedge_active.astype(bool),alpha=.2,label='Stress state')
    axes[2].set(ylabel='Annualized estimated volatility');axes[2].legend()
    fig.tight_layout(); fig.savefig(figures/'hedging_states.svg',metadata={'Date':None});fig.savefig(figures/'hedging_states.png',dpi=140);plt.close(fig)
    examples=pd.read_csv(out/'simulation_examples.csv',parse_dates=['date'])
    fig,ax=plt.subplots(figsize=(11,5))
    for name,g in examples.groupby('strategy'):
        for path,h in g.groupby('path'):
            if path<5:ax.plot(h.date,h.nav/7e6,alpha=.3,label=name if path==0 else None)
    ax.set(title='Predefined scenario IDs 0-4 | combined net marked NAV',ylabel='NAV (700m = 100)');ax.legend();fig.tight_layout()
    fig.savefig(figures/'hedging_scenarios.svg',metadata={'Date':None});fig.savefig(figures/'hedging_scenarios.png',dpi=140);plt.close(fig)
    for p in figures.glob('*.svg'):p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    text='''# 獨立風險驅動避險研究

原股票帳戶為 5 億美元，維持原始 12 隻股票及買入持有規則。新增 2 億美元獨立帳戶，合併起始資本 7 億美元。股票帳戶只計算一次，各避險策略共用完全相同的股票持倉及損益。這個基準選擇與再平衡頻率研究分開，不因已知績效選擇最佳頻率。

## 工具與規則

H0：額外資金保留 2% 現金緩衝，其餘買入 SGOV。H1：持續配置 SH，餘額 SGOV。H2：正常狀態持 SGOV；高風險且市場下降狀態轉入 SH；狀態解除時回到 SGOV。只在狀態改變時調整，避免把每日檢查等同每日交易。

SH 是每日 -1x S&P 500 反向 ETF；它持有期貨及交換合約，帳戶本身只買入 ETF，不交易期權。SH 不是現金等價物，跨日報酬有每日重設與複利效應。SGOV 持有 0–3 月國債，提供儲備功能。SPY 只作訊號與 beta 估計。ETF 工具只新增到獨立避險帳戶，原股票帳戶維持 stocks-only。

風險模型為可解釋的正常／壓力雙狀態模型。原目標股票報酬的 EWMA 年化風險超過訓練分布第 75 百分位，且 SPY 過去 21 段報酬累積為負時進入壓力狀態；風險低於第 50 百分位或趨勢轉正時退出。0.94 衰減、21 日趨勢及 75/50 百分位是預先宣告的探索假設，沒有經獨立樣本驗證為最佳。截止日後只更新狀態，不重新估計門檻或 beta。

SH 目標金額為預先估計並截限至 [0,1] 的股票組合對 SPY beta × 5 億美元，上限為當時避險帳戶扣除 2% 緩衝後的金額。因此可能只能部分抵銷股票市場敏感度，個股及空倉急升風險仍存在。交易以訊號日收市資料決定固定數量，下一交易日調整後收市價成交；初始建倉使用訓練末狀態。最後一日優先假設清倉。

## 歷史診斷結果

'''+actual.to_markdown(index=False,floatfmt='.6f')+'''

![風險狀態與績效](figures/hedging_states.svg)

## 10,000 個共同區塊抽樣情境

股票、基準、SGOV、SH、SPY 使用完全相同歷史日期區塊，保留共同變動。每條路徑獨立過濾狀態；未來價格不得影響較早交易。所有策略使用相同 7 億美元資本，H0 是衡量避險增值的公平比較基準。

'''+summary.to_markdown(index=False,floatfmt='.6f')+'\n\n'+pairs.to_markdown(index=False,floatfmt='.6f')+'''

![共同情境範例](figures/hedging_scenarios.svg)

## 資料與限制

- 訓練：2024-04-29 至 2026-04-28；評估：2026-05-01 至 2026-08-03，63 段報酬。先凍結模型並完成模擬，才載入評估價格。
- 新工具價格為 2026-10-27 下載的 Yahoo 調整後收市價，股息及基金內費用已反映在價格報酬；不再加計股息或另扣基金費用。原股票資料來源及公司行動仍未獨立驗證。
- 原股票帳戶現金、空倉所得與抵押繼續獨立記帳；2 億美元是新增資本，沒有跨帳戶挪用或注資。股票費用沿用 10 bps 與示意 2% 年借券費。
- ETF 交易成本為示意 10 bps 實際交易額。2% 現金緩衝是研究假設；若固定訂單在價差後資金不足，拒絕整筆轉倉、保留持倉、記錄拒單，下一日以新取得的前收市資訊重試；無假設融資、追溯縮單或刪除路徑。
- 本研究是調整後價格理想化診斷，使用合成分數單位；不代表已驗證的開盤成交或券商實盤。2 億美元 SH 訂單的市場容量、價差及衝擊尚未驗證。
- 2026 評估結果早已被研究過；這是歷史診斷比較，工具與模型也是回顧性研究選擇。原計算、notebook、再平衡分支與輸出均保留。
- SH 官方：https://www.proshares.com/our-etfs/leveraged-and-inverse/sh
- SGOV 官方：https://www.ishares.com/us/products/314116/ishares-0-3-month-treasury-bond-etf
'''
    (out/'report.md').write_text(text,encoding='utf-8')
