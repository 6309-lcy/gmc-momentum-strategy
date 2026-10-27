"""Frequency-by-hedge figures and research report."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import pandas as pd


FREQUENCIES = [('BH', 'Buy and hold'), ('M', 'Monthly'),
               ('D', 'Daily'), ('W', 'Every 5 observations')]
HEDGES = [('H0', 'SGOV reserve'), ('H1', 'Static SH'), ('H2', 'Dynamic SH')]
COLORS = {'H0': 'tab:blue', 'H1': 'tab:orange', 'H2': 'tab:green'}


def _save_figure(fig, figures, name):
    fig.tight_layout()
    fig.savefig(figures/f'{name}.svg', metadata={'Date': None})
    fig.savefig(figures/f'{name}.png', dpi=140)
    plt.close(fig)


def write_report(out, config, model, actual, summary, pairs):
    out = Path(out)
    figures = out/'figures'
    figures.mkdir(exist_ok=True)
    total = config['stock_capital'] + config['overlay_capital']
    nav = pd.read_csv(out/'daily_nav.csv', parse_dates=['date'])
    signals = pd.read_csv(out/'signals.csv', index_col=0, parse_dates=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True, sharey=True)
    drawdown_fig, drawdown_axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True, sharey=True)
    for (frequency, title), ax, drawdown_ax in zip(FREQUENCIES, axes.flat, drawdown_axes.flat):
        for hedge, label in HEDGES:
            name = f'{frequency}_{hedge}'
            g = nav.loc[nav.strategy == name].sort_values('date')
            if g.empty:
                raise ValueError(f'Missing historical strategy: {name}')
            values = pd.Series(g.performance_nav.to_numpy(), index=g.date)
            ax.plot(values.index, values/total*100, color=COLORS[hedge], label=f'{hedge}: {label}')
            peak = values.cummax().clip(lower=total)
            drawdown_ax.plot(values.index, values/peak-1, color=COLORS[hedge], label=f'{hedge}: {label}')
        ax.set(title=f'{frequency} | {title}', ylabel='Combined NAV (700m = 100)')
        drawdown_ax.set(title=f'{frequency} | {title}', ylabel='Drawdown from initial capital / peak')
        drawdown_ax.yaxis.set_major_formatter(PercentFormatter(1))
        for panel in (ax, drawdown_ax):
            panel.legend(fontsize=8)
            panel.grid(alpha=.2)
            panel.tick_params(axis='x', labelrotation=25)
    fig.suptitle('Original stocks + scheduled rebalancing + 200m overlay | historical diagnostic')
    drawdown_fig.suptitle('Combined-account drawdowns | terminal hypothetical liquidation included')
    _save_figure(fig, figures, 'hedging_states')
    _save_figure(drawdown_fig, figures, 'hedging_drawdowns')

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(signals.index, signals.volatility, label='Fixed-original-target EWMA volatility')
    axes[0].axhline(model['entry_threshold'], color='tab:red', linestyle='--', label='Frozen entry threshold')
    axes[0].axhline(model['exit_threshold'], color='tab:green', linestyle=':', label='Frozen exit threshold')
    axes[0].fill_between(signals.index, 0, signals.volatility.max(),
                         where=signals.hedge_active.astype(bool), alpha=.2, label='Stress state at close')
    axes[0].set(ylabel='Annualized estimated volatility', title='Shared risk signal | independent of stock rebalance frequency')
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].plot(signals.index, signals.trend_21, label='SPY trailing 21-return trend')
    axes[1].axhline(0, color='grey', linewidth=.8)
    axes[1].set(ylabel='Cumulative return', xlabel='Observed close (orders execute next session)')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    _save_figure(fig, figures, 'risk_states')

    examples = pd.read_csv(out/'simulation_examples.csv', parse_dates=['date'])
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True, sharey=True)
    for name, ax in zip(['M_H0', 'M_H2', 'D_H2', 'W_H2'], axes.flat):
        for path in range(5):
            g = examples.loc[(examples.strategy == name) & (examples.path == path)].sort_values('date')
            ax.plot(g.date, g.nav/total*100, alpha=.65, label=f'Path {path}')
        ax.set(title=name, ylabel='Combined marked NAV (700m = 100)')
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
        ax.tick_params(axis='x', labelrotation=25)
    fig.suptitle('Predefined common scenario IDs 0–4 | illustrative paths, not performance-selected')
    _save_figure(fig, figures, 'hedging_scenarios')
    for name in ['hedging_states', 'hedging_drawdowns', 'risk_states', 'hedging_scenarios']:
        p = figures/f'{name}.svg'
        p.write_text('\n'.join(x.rstrip() for x in p.read_text(encoding='utf-8').splitlines())+'\n', encoding='utf-8')
    text = '''# 原有股票、再平衡與獨立避險帳戶研究

原股票帳戶為 5 億美元，保留原始 12 隻股票及凍結目標權重，結合預定再平衡規則與新增 2 億美元獨立避險帳戶。每個策略合併起始資本均為 7 億美元。先前只以買入持有股票搭配避險的初始分支定義已被本設計取代；BH 現在是保留的參考組。

## 固定股票目標與 12 個策略

| 股票規則 | 再平衡時程 | 避險策略代碼 |
| --- | --- | --- |
| BH | 初始建倉後買入持有 | BH_H0、BH_H1、BH_H2 |
| M | 每月首個觀察交易日 | M_H0、M_H1、M_H2 |
| D | 每個後續觀察交易日 | D_H0、D_H1、D_H2 |
| W | 自起點起每 5 個觀察值，並非曆週 | W_H0、W_H1、W_H2 |

各時程均排除初始建倉日及最終清倉日的例行再平衡。再平衡回到原始凍結權重，不重新選股或最佳化權重；以執行日前一收市的股票淨值及價格決定固定股數，在執行日調整後收市價成交。初始股票建倉使用首日調整後收市價，是診斷假設。

同一頻率的 H0／H1／H2 共用相同股票交易、成本與股票淨值；不同頻率則有各自的股票交易與成本。所有頻率對同一避險模式共用完全相同的 2 億美元帳戶路徑，這是刻意的控制設計：風險訊號只依固定原目標權重組合，不依再平衡後實際持倉或合併帳戶淨值。這不是各頻率即時曝險的個別最適避險；報表另量度各合併帳戶的實際波動與回撤。

## 工具與規則

H0：額外資金保留 2% 現金緩衝，其餘買入 SGOV。H1：持續配置 SH，餘額 SGOV。H2：正常狀態持 SGOV；高風險且市場下降狀態轉入 SH；狀態解除時回到 SGOV。只在狀態改變時調整，避免把每日檢查等同每日交易。

SH 是每日 -1x S&P 500 反向 ETF；它持有期貨及交換合約，帳戶本身只買入 ETF，不交易期權。SH 不是現金等價物，跨日報酬有每日重設與複利效應。SGOV 持有 0–3 月國債，提供儲備功能。SPY 只作訊號與 beta 估計。ETF 工具只新增到獨立避險帳戶，原股票帳戶維持 stocks-only。

風險模型為可解釋的正常／壓力雙狀態模型。原目標股票報酬的 EWMA 年化風險超過訓練分布第 75 百分位，且 SPY 過去 21 段報酬累積為負時進入壓力狀態；風險低於第 50 百分位或趨勢轉正時退出。0.94 衰減、21 日趨勢及 75/50 百分位是預先宣告的探索假設，沒有經獨立樣本驗證為最佳。截止日後只更新狀態，不重新估計門檻或 beta。

SH 目標金額為預先估計並截限至 [0,1] 的原目標股票組合對 SPY beta × 5 億美元，上限為當時避險帳戶扣除 2% 緩衝後的金額。因此可能只能部分抵銷股票市場敏感度，個股及空倉急升風險仍存在。避險交易以訊號日收市資料決定固定合成分數單位，下一交易日調整後收市價成交；初始避險建倉使用訓練末狀態。最後一日優先假設清倉。

## 歷史診斷結果

下表逐一列出 12 個策略。績效曲線使用 performance_nav，含末日假設清倉成本；平日為合併淨值。combined_nav 則為清倉前按市值計算的股票與避險帳戶淨值合計。

'''+actual.to_markdown(index=False, floatfmt='.6f')+'''

![各頻率三種避險模式的合併績效](figures/hedging_states.svg)

![各頻率合併帳戶回撤](figures/hedging_drawdowns.svg)

![所有頻率共用的固定目標風險訊號](figures/risk_states.svg)

風險狀態圖標示當日收市後的狀態；對應訂單於下一觀察交易日執行，陰影不是當日已成交持倉。

## 10,000 個共同區塊抽樣情境

股票、基準、SGOV、SH、SPY 使用完全相同歷史日期區塊，保留共同變動。每條路徑獨立過濾狀態並套用四種股票時程；未來價格不得影響較早交易。所有 12 個策略使用相同 7 億美元資本。

'''+summary.to_markdown(index=False, floatfmt='.6f')+'''

配對差異使用同一路徑的淨報酬。每個頻率分別比較 H2−H0 與 H1−H0，衡量固定股票交易下的避險效果；M／D／W 的 H2 分別減去 BH_H2，衡量相同動態避險帳戶下的再平衡效果；M／D／W 的 H0 分別減去 BH_H0，衡量相同儲備帳戶下的再平衡效果。差異為報酬率差，正值頻率不等同風險全面改善，也不據此回選最佳頻率。

'''+pairs.to_markdown(index=False, floatfmt='.6f')+'''

![M_H0、M_H2、D_H2、W_H2 的共同情境 0–4](figures/hedging_scenarios.svg)

範例固定展示前五個情境，未依結果挑選；曲線為清倉前按市值計算的合併淨值，末日清倉成本由績效表另行反映。

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
    (out/'report.md').write_text(text, encoding='utf-8')
