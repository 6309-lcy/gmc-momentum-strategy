# GMC Momentum Portfolio Research

A stocks-only long/short portfolio built from chronological strategy validation, constrained optimisation, and Monte Carlo forecasts. This repository contains the selected **momentum strategy with risk penalty 2**, its executable analysis, frozen allocation, and supporting results.

**Recorded diagnostic return, 1 May–9 October 2026: +34.71% gross and +34.29% after illustrative costs**, compared with **+2.63%** for the Fund X proxy. Starting equity is $500 million. These are modelled returns from saved adjusted-price data. The evaluation period had already been explored during research, and the input data's provenance and corporate-action adjustments have not been independently verified.

![Portfolio NAV, P&L, and drawdown through 9 October 2026](aligned_method/validated_strategy/performance_to_9_oct.svg)

## Recorded results

| Period | Portfolio gross | After assumed costs | Fund X proxy | Gross P&L |
|---|---:|---:|---:|---:|
| 1 May–3 August 2026 · 63 return intervals | +4.59% | +4.28% | +0.23% | +$22.95m |
| 1 May–9 October 2026 · 111 return intervals | +34.71% | +34.29% | +2.63% | +$173.56m |

The extended period has **34.32% annualised gross volatility** and **−9.63% maximum gross drawdown**. The original three-month Monte Carlo forecast has a gross mean return of **+2.52%** and a 5th–95th percentile range of **−11.74% to +18.47%**. The October evaluation extends beyond that forecast horizon.

![Holding-level profit and loss](aligned_method/validated_strategy/attribution_to_9_oct.svg)

**Profit concentration matters:** MRNA contributes $147.73m, approximately 85% of the total gross P&L. Its saved adjusted-price return is +395.92% over the extended period. That observation warrants independent data verification before drawing conclusions about repeatability.

## Scope and portfolio rules

The candidate universe is a fixed allowlist of **123 operating-company stock tickers** represented in the supplied historical data. It spans technology, healthcare, finance, industrials, and energy, including US companies and internationally headquartered issuers represented by their supplied tickers. The scope is bounded by this allowlist and the available price history. The full list appears as `stock_allowlist` in [analysis.py](analysis.py), and its price series are included in [data/](data/).

For the final two-year estimation window, **119 stocks pass the eligibility screen**. Candidates require at least 98% daily-return coverage, positive prices, and a maximum absolute daily return of 40% within the window. BE, DXCM, and RUN fail these filters; FOLD is excluded because its acquisition completed before entry. Both long and short candidates come from the eligible stock universe. The selected portfolio holds eight longs and four shorts. ETFs, bonds, commodities, currencies, and derivatives are outside the portfolio's current investment universe. The Fund X comparison uses separate benchmark instruments.

This is a **buy-and-hold strategy**: the portfolio enters once on 1 May 2026 and holds the initial share quantities through each evaluation endpoint. Position weights drift as prices change. Each selected stock's **initial net position has an absolute size of at least 5% and at most 15% of starting equity**: longs carry positive weights and shorts carry negative weights. The minimum applies at entry; subsequent price changes can move weights outside that range. The total initial portfolio net exposure is 60%, with 80% long exposure and 20% short exposure.

**Transaction costs (TC)** are assumed to be **10 basis points (0.10%) of traded notional at entry and at each evaluation's hypothetical exit**. Exit costs use the ending position values. Short borrowing costs are **2% per year on the initial short notional**, accrued using elapsed daily-return intervals divided by 252. The after-cost figures include these charges. Cash earns zero interest; taxes, additional financing charges, and a separate market-impact or slippage model are outside the accounting scope.

## Strategy

At every historical allocation date, the model uses the preceding two years of prices. Nine rule/penalty combinations are compared over 13 chronological blocks of 63 daily returns. Momentum with risk penalty 2 has the highest validation selection score; its recorded cumulative validation return after assumed costs is +105.15% across 819 daily returns.

The momentum score combines twelve-month momentum excluding the latest 21 sessions (35%), six-month momentum excluding the latest 21 sessions (30%), recent three-month momentum (15%), and six-month momentum relative to sector peers (20%). Cross-sectional ranks temper extreme observations. Ledoit–Wolf covariance and constrained optimisation translate the scores into weights.

| Initial constraint | Setting |
|---|---|
| Instruments | Operating-company stocks |
| Gross exposure / starting equity | $500m / $500m |
| Long / short exposure | 80% / 20% |
| Holdings | 8 long, 4 short |
| Absolute position size | 5%–15% |
| Sector gross exposure cap | 45% |
| Final estimation window | 29 April 2024–28 April 2026 |
| Portfolio accounting | Fixed initial units; zero-interest cash |
| Illustrative costs | 10 bps at entry and exit; 2% annual borrow on initial shorts |

Risk enters through the variance penalty and exposure limits. The selected strategy has no hard volatility ceiling. Holdings drift with prices after entry. Fund X is a daily-rebalanced public proxy: 20% `^SPGSCI`, 50% `URTH`, and 30% `BNDW`. Portfolio holdings remain stocks-only.

![Validation selection scores and initial weights](aligned_method/validated_strategy/validation_and_weights.svg)

## Reproduce

Use Python 3.11 or newer, from this repository's root:

```bash
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies and verify the published results without network access:

```bash
python -m pip install -r requirements.txt
python report.py
```

`report.py` independently rebuilds both evaluation paths from saved prices and checks the frozen-weight SHA-256, exposure constraints, selected validation winner, training cutoff, returns, illustrative costs, benchmark, volatility, drawdown, and holding attribution. It also regenerates all four SVG figures.

To rerun historical model selection, portfolio construction, the 10,000-path forecast, and both evaluations:

```bash
python analysis.py
```

The runner writes results into `aligned_method/validated_strategy/`. Saved evaluation price caches make the recorded date ranges reproducible offline. If those caches are removed, the runner attempts to download prices with `yfinance`; availability and vendor revisions may affect the result. Dependency ranges allow compatible installations; numerical optimiser outputs can vary slightly across versions. The published weight hash identifies the recorded allocation.

The [executed notebook](GMC_Validated_Strategy.ipynb) presents the same analysis with its recorded tables (figures render when rerun). Open it with `jupyter lab`. Run it from the repository root, and restart the kernel before executing all cells.

![Three-month forecast compared with diagnostic performance](aligned_method/validated_strategy/forecast_vs_diagnostic.svg)

## Repository contents

| File | Purpose |
|---|---|
| [analysis.py](analysis.py) | Full strategy selection, optimisation, forecasts, and evaluation |
| [report.py](report.py) | Offline accounting verification and README charts |
| [GMC_Validated_Strategy.ipynb](GMC_Validated_Strategy.ipynb) | Selected strategy's executed research notebook |
| [METHODOLOGY.md](METHODOLOGY.md) | Detailed method, portfolio table, assumptions, and interpretation |
| [data/](data/) | Monthly stock-universe training CSVs from January 2021 through the information cutoff |
| [aligned_method/validated_strategy/](aligned_method/validated_strategy/) | Frozen strategy and weights, cached evaluation prices, CSV tables, and figures |

The monthly training CSVs preserve the source values for the operating-company allowlist and the dates needed by this strategy. Earlier unused history and instruments outside the strategy's universe are omitted.

## Rebalancing and initial risk research

The `with-rebalancing` branch adds [GMC_Rebalancing_Analysis.ipynb](GMC_Rebalancing_Analysis.ipynb), a shared accounting engine, pre-cutoff risk diagnostics, monthly frozen-target policies, 10,000 paired joint-bootstrap scenarios, and historical replay. The original analysis and published outputs remain available.

```bash
python -m unittest discover -s tests -v
python run_rebalancing.py
```

Open the executed notebook for the standalone analysis, or read [the comparison report](aligned_method/rebalancing/report.md). [REBALANCING_DESIGN.md](REBALANCING_DESIGN.md) documents the contracts. Outputs include orders, trades, costs, daily NAV, attribution, paired comparisons, and a data/source-hash manifest.

Execution uses an **idealized adjusted-close diagnostic** with preceding-close sizing for the June 1 and July 1 trades. Initial entry is May 1; hypothetical liquidation is August 3. The fixed XNYS calendar yields 63 return intervals. P2/P3 remain explicitly unconfigured until a justified predeclared risk budget is set in `rebalancing/config.json`. All nine policy IDs appear in reports. P4 adds daily fixed-target trading and P5 adds five-session trading. P6/P7 support explicitly configured risk- and drawdown-triggered reductions. Each simulated path updates its own risk estimate using completed returns, initialized from pre-cutoff Ledoit–Wolf covariance. The notebook includes price and volatility fans for all 12 stocks plus portfolio NAV/risk/drawdown plots. The comparison uses illustrative financing and fees and a previously explored historical period.

## 獨立避險研究（hedging 分支）

[GMC_Hedging_Analysis.ipynb](GMC_Hedging_Analysis.ipynb) 與 [HEDGING_DESIGN.md](HEDGING_DESIGN.md) 將避險任務獨立管理。原股票帳戶保留 5 億美元配置；新增 2 億美元在 SGOV 儲備與 SH 反向 ETF 之間，依只使用過去資訊的雙狀態風險模型切換。帳戶不交易期權，SH 基金內使用衍生工具。模型、工具及門檻屬回顧性探索研究假設。

執行 `python run_hedging.py` 重建 10,000 個共同情境、歷史診斷、帳戶明細與圖表。結果存於 [aligned_method/hedging/report.md](aligned_method/hedging/report.md)。此任務不修改原再平衡策略或其輸出。

## Further improvement

The following extensions are proposed research directions. The reported results use the current buy-and-hold strategy.

| Direction | Possible implementation | Evaluation focus |
|---|---|---|
| Hedging strategy | Add index futures or protective puts to manage market exposure; size hedges against portfolio beta or a drawdown budget. | Drawdown reduction, hedge carry, option premiums, margin, and performance after costs. |
| Rebalancing rules | Compare monthly or quarterly rebalancing with weight-drift bands and signal-change triggers. Apply position and exposure constraints at each rebalance. | Turnover, transaction costs, signal persistence, and net performance. |
| Expanded risk model | Extend the existing Ledoit–Wolf covariance model with market, sector, country, currency, and style factors; add volatility targets, expected shortfall, and stress scenarios. | Factor concentration, tail losses, exposure stability, and forecast calibration. |
| Market-regime model | Use a Markov chain or hidden Markov model to estimate transitions between market regimes, such as trending, volatile, and defensive conditions. Let estimated regime probabilities influence gross exposure, risk penalties, and hedge size. | Fit using information available at each decision date; assess state stability and performance in subsequent periods. |
| Regional allocation model | Group issuers by economic geography and currency exposure; add regional limits, regional momentum signals, and FX hedging rules. | Regional concentration, currency risk, and diversification across market cycles. |

Evaluate each extension with chronological walk-forward comparisons against the frozen buy-and-hold baseline, including its additional trading and financing costs.
