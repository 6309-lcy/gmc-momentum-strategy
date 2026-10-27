# Portfolio Rebalancing and Risk Management

Status: implemented first diagnostic version. Branch: `with-rebalancing`.

## Purpose and information boundary

Compare monthly fixed-target rebalancing with the frozen momentum buy-and-hold portfolio, using $500 million equity. Preserve the existing holdings, momentum scores, rankings, weight constraints, analysis scripts, notebooks, and published results. The original exposure is 80% long and 20% short. Returns after costs, risk, and benchmark comparisons determine the research findings; outperformance is a research objective.

Training runs April 29, 2024–April 28, 2026. Policy freezing, covariance, block length, scenario calibration, and optional risk scaling use this panel exclusively. Freeze and hash the policy before simulations and before loading evaluation prices. Evaluation prices serve mechanical sizing, fills, valuation, and performance measurement. The evaluation period was previously explored and supplies historical diagnostic evidence.

## Clock and execution contract

The fixed XNYS exchange calendar gives 64 closes from May 1 through August 3, 2026, hence 63 close-to-close return intervals. Establish the portfolio May 1. Subsequent monthly fill dates are June 1 and July 1. August 3 hypothetical terminal liquidation takes precedence over a monthly rebalance.

The saved data contain adjusted closes. Version one uses an explicitly idealized close-price diagnostic: initial entry uses fractional synthetic units at the initial adjusted close; each later monthly order uses preceding-close NAV and prices, rounds its change in quantity to the nearest whole synthetic unit, then fills that fixed order at the scheduled adjusted close. Record fees and resulting weight deviations. Price adjustments represent dividend reinvestment proxies and signed short dividend effects; no separate dividends are added. Synthetic adjusted units require raw action-level data before executable-share interpretation. Verified next-open execution remains dependent on obtaining coherent open/close and corporate-action records.

## Predefined policies

| ID | Definition |
|---|---|
| B0 | Daily-rebalanced Fund X proxy: 20% ^SPGSCI, 50% URTH, 30% BNDW |
| P0 | Original frozen weights, buy-and-hold |
| P1 | Original weights, monthly fixed-target rebalancing |
| P2 | Initially risk-scaled weights, buy-and-hold |
| P3 | Initially risk-scaled weights, monthly rebalancing |

P2/P3 use k = min(1, risk_budget / pre-cutoff Ledoit–Wolf annual volatility). Freeze k. Released exposure remains cash. These are relaxed-exposure variants that can fall below the original minimum holding weights. A null risk budget leaves P2/P3 explicitly unconfigured. Tracking error remains diagnostic. Every predefined policy appears in reports.

Pre-cutoff diagnostics include Ledoit–Wolf covariance, volatility, gross/net/sector exposure, holding and sector concentration, stock risk contributions, URTH beta, Fund X beta and tracking error, and worst rolling 5-, 21-, and 63-session stress returns. Stress returns compound constant-weight returns within the training sample.

## Accounting and financing

One engine handles simulations and historical replay. NAV equals cash plus signed quantities times prices. Transaction fees are 10 basis points of actual traded notional, including entry and hypothetical exit. Borrow is an illustrative 2% annual rate on previous-close outstanding short market value, accrued over actual calendar days divided by 365. Cash interest is zero. Short proceeds enter cash, current short market value is restricted collateral, and available cash is cash minus collateral. Reject insufficient available cash and nonpositive NAV; never inject capital. Further margin, borrow availability, and market impact require independent execution work.

Report marked-to-market and hypothetical liquidation values; net comparisons use liquidation. Maintain an independent zero-cost ledger with its own causal order sizes. Preserve published accounting, which charges borrow on initial shorts using elapsed return intervals/252, and reconcile gross paths and net-return differences explicitly. Missing, duplicate, nonpositive, or off-calendar prices cause explicit failure without filling.

## Joint bootstrap and evaluation

Use 10,000 paths and a fixed seed. Align all 15 asset histories without imputation. Each scenario resamples common contiguous historical blocks across stocks and benchmark components. Choose block length by a recorded pre-cutoff autocorrelation rule: one plus the largest significant lag in portfolio returns or squared returns over lags 1–20, capped at 21. Normalize starting simulated levels to the last pre-cutoff asset prices so whole-unit rounding has a meaningful fixed basis. Use the same calendar, execution, and accounting contracts for every strategy and replay.

Publish mean, median, 5th/95th net returns, excess returns, outperformance and loss frequencies, drawdown distribution summaries, worst 5% average return, turnover, transaction/borrow costs, and paired differences P1−P0, P2−P0, P3−P2. Archive scenario samples and explicit execution failures. Interpret outperformance as the proportion of scenarios outperforming Fund X under the specified historical sample and simulation assumptions.

Historical evaluation reports gross/net returns, excess return, drawdown, volatility, tracking error, turnover, costs, stock contributions, actual-result simulation percentile, and data warnings. Fund X is a proxy reference with mixed index-price and adjusted ETF return conventions. ^SPGSCI is an index and requires an executable substitute for implementation.

## Modules and deliverables

`data_access.py` enforces boundaries and calendars; `policies.py` freezes targets and schedules; `risk_model.py` estimates diagnostics; `execution.py` specifies rounding; `accounting.py` keeps ledgers; `simulation.py` produces joint paired paths; `evaluation.py` replays historical prices; `reporting.py` writes audit files, tables, narrative, and figures. `run_rebalancing.py` coordinates stages. `GMC_Rebalancing_Analysis.ipynb` presents an executed standalone analysis.

Outputs live in `aligned_method/rebalancing/`: manifest, frozen policy, risk diagnostics, simulation summaries and scenario samples, paired comparisons, daily NAV, orders, trades, costs, attribution, actual metrics, baseline reconciliation, warnings, report, and figures. The manifest identifies code revision plus source hashes, data hashes, dependencies, configuration, seed, and execution assumptions.

## Verification and extension boundary

Tests cover strict cutoff/calendar enforcement, policy isolation and tampering, causal orders, self-financing signed accounting, constant-price behavior, costs, joint scenario indices, reproducibility, published baseline reproduction, and execution consistency. Run `python -m unittest discover -s tests -v`, then `python run_rebalancing.py`. Original reproduction remains `python report.py`.

The user subsequently extended scope to causal daily/weekly decisions and evolving risk estimates. P4 restores original targets daily; P5 restores targets every five observed sessions (first fill on observation 6). P6 supports a ratcheted reduction against a configured annual volatility budget; P7 supports a one-time configured drawdown reduction with no re-entry. P6/P7 default to unconfigured. Thresholds, responses and estimator settings are frozen before simulation and replay.

Covariance begins with the pre-cutoff Ledoit–Wolf estimate and updates after each completed return by a zero-mean EWMA second moment, with declared decay 0.94. Decision t uses state through t−1. Every path has its own market and portfolio state. Stock selection and original relative target weights remain frozen. Terminal liquidation suppresses fresh decisions. Asset price and estimated-volatility fans cover all 12 members; portfolio fans show marked NAV, volatility and drawdown with pointwise quantiles and predefined example paths.

Stock replacement, regime switches and evaluation-driven parameter selection remain outside scope. A complete opening-price implementation requires suitable verified data. Configured P2/P3 require a justified initial risk budget; configured P6/P7 require justified dynamic thresholds and explicit responses.
