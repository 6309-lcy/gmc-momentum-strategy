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

## Research limitations

Validation observations determine the selected rule. The 2026 period had also been inspected in earlier research. Both facts limit the independence of the reported evidence. This repository presents the strongest recorded strategy from the project, so retrospective selection across experiments also affects interpretation.

The source training file is named `synthetic_prices.csv`; its provenance and corporate-action handling remain unverified. The stock universe can introduce survivorship bias. Forecast expected-return scaling and normal-return assumptions are modelling choices. Short availability, liquidity, and execution at $500m scale are unverified. Costs are illustrative; cash interest, taxes, and additional financing charges are omitted. Recorded figures represent research calculations rather than verified brokerage performance or a guarantee of future returns.
