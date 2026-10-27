# Portfolio rebalancing and initial risk positioning

This historical diagnostic compares the frozen momentum portfolio with monthly, daily, and five-session fixed-target rebalancing, with configurable risk- and loss-triggered exposure reductions. Starting equity is $500,000,000. Entry uses the 1 May 2026 adjusted close; the endpoint uses the 3 August 2026 adjusted close. There are 64 valuation observations and 63 close-to-close return intervals on the fixed XNYS calendar.

The monthly execution dates are 2026-06-01, 2026-07-01. Orders use the preceding session's prices and NAV. Fixed quantities fill at the next scheduled adjusted close. The first portfolio allocation is a same-close idealization. Fractional quantities represent synthetic dividend-adjusted units. These results are idealized close-price diagnostics. Verified opening execution requires a separate coherent open, close, split, and dividend dataset.

## Historical comparison

Primary net returns include entry, actual rebalance trades, daily outstanding-short borrowing, and hypothetical terminal liquidation costs. Marked-to-market returns retain the open positions. Gross returns use a parallel zero-cost ledger with its own causal NAV sizing.

| strategy   | status                                                         |   net_return |   max_drawdown |   realized_volatility |   gross_return |   mtm_net_return |   excess_return |   tracking_error |   turnover |   transaction_cost |   terminal_liquidation_cost |   borrow_cost |   simulation_percentile |
|:-----------|:---------------------------------------------------------------|-------------:|---------------:|----------------------:|---------------:|-----------------:|----------------:|-----------------:|-----------:|-------------------:|----------------------------:|--------------:|------------------------:|
| B0         | proxy benchmark                                                |     0.002294 |      -0.045120 |              0.077475 |       0.002294 |         0.002294 |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |               20.040000 |
| P0         | historical close-price diagnostic                              |     0.042756 |      -0.089073 |              0.286604 |       0.045894 |         0.043841 |        0.040462 |         0.251930 |   2.039668 |      500000.000000 |               542624.233847 | 526100.776027 |               41.010000 |
| P1         | historical close-price diagnostic                              |     0.078810 |      -0.063309 |              0.255826 |       0.082282 |         0.079894 |        0.076516 |         0.226919 |   2.259007 |      634752.715415 |               542034.741420 | 522616.349748 |               53.450000 |
| P2         | unconfigured: initial risk budget required                     |   nan        |     nan        |            nan        |     nan        |       nan        |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |              nan        |
| P3         | unconfigured: initial risk budget required                     |   nan        |     nan        |            nan        |     nan        |       nan        |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |              nan        |
| P4         | historical close-price diagnostic                              |     0.046399 |      -0.067090 |              0.257000 |       0.051318 |         0.047471 |        0.044105 |         0.227955 |   3.677831 |     1366193.609777 |               535723.031274 | 539566.486642 |               42.860000 |
| P5         | historical close-price diagnostic                              |     0.050779 |      -0.068785 |              0.258414 |       0.054752 |         0.051845 |        0.048485 |         0.228979 |   2.772027 |      898309.533407 |               532754.877307 | 535772.266816 |               44.140000 |
| P6         | unconfigured: dynamic risk budget required                     |   nan        |     nan        |            nan        |     nan        |       nan        |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |              nan        |
| P7         | unconfigured: drawdown threshold and reduction factor required |   nan        |     nan        |            nan        |     nan        |       nan        |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |              nan        |

![Historical NAV](figures/historical_nav.svg)

Flag symbols identify actual nonzero rebalance fills on each historical portfolio line. Initial entry and terminal liquidation have no flags. Buy-and-hold lines have no flags. Simulation flags mark frozen scheduled rebalance execution dates on the median and each displayed example path; median curves are pointwise summaries. Asset price/volatility panels describe the common market and carry no portfolio-specific event flags.

P2 and P3 are relaxed-exposure variants. Their default status is unconfigured because no independently justified volatility budget has been supplied. The pipeline supports a positive predeclared `risk_budget` in the configuration; it freezes the scale before simulation and historical replay. All nine predefined strategy IDs remain visible in the output tables. P4 rebalances daily using the preceding close; P5 rebalances after each five completed observations (first fill at observation 6, then 11, 16, and so on). P6 checks previous-close estimated portfolio volatility against `dynamic_risk_budget` and ratchets target exposure downward; P7 reduces exposure once after previous-close drawdown breaches `loss_drawdown_threshold`, using `loss_reduction_factor`, with no re-entry. P6/P7 remain unconfigured until their respective thresholds and responses are explicitly set before evaluation.

## Paired historical-bootstrap scenarios

The joint bootstrap draws 10,000 scenarios with seed 20260428, using contiguous blocks of 13 daily return observations. Each asset and each strategy receives the same sampled historical dates. The frozen policy records the pre-cutoff block-length rule. This is a historical-resampling forecast and does not establish predictive momentum excess returns.

| strategy   | status                                                         |    scenarios |   failed_scenarios |   mean_net_return |   median_net_return |   p05_net_return |   p95_net_return |   mean_excess_return |   outperformance_frequency |   loss_frequency |   worst_5pct_mean_return |   mean_max_drawdown |   p05_max_drawdown |   p95_max_drawdown |   mean_turnover |   mean_transaction_cost |   mean_terminal_liquidation_cost |   mean_borrow_cost | statistics_basis   |
|:-----------|:---------------------------------------------------------------|-------------:|-------------------:|------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|-----------------:|-------------------------:|--------------------:|-------------------:|-------------------:|----------------:|------------------------:|---------------------------------:|-------------------:|:-------------------|
| B0         | configured                                                     | 10000.000000 |           0.000000 |          0.033684 |            0.035342 |        -0.035172 |         0.096218 |             0.000000 |                   0.000000 |         0.186200 |                -0.056331 |           -0.036078 |          -0.086904 |          -0.012567 |        0.000000 |                0.000000 |                       nan        |           0.000000 | all scenarios      |
| P0         | configured                                                     | 10000.000000 |           0.000000 |          0.075519 |            0.071375 |        -0.108123 |         0.279991 |             0.041835 |                   0.626800 |         0.271200 |                -0.148028 |           -0.081017 |          -0.162530 |          -0.031408 |        1.995280 |           500000.000000 |                    535235.533631 |      509642.697065 | all scenarios      |
| P1         | configured                                                     | 10000.000000 |           0.000000 |          0.073200 |            0.068518 |        -0.107349 |         0.271599 |             0.039515 |                   0.619700 |         0.272400 |                -0.148294 |           -0.080398 |          -0.161810 |          -0.030797 |        2.166441 |           587588.988885 |                    535724.991525 |      524962.191517 | all scenarios      |
| P2         | unconfigured: initial risk budget required                     |   nan        |         nan        |        nan        |          nan        |       nan        |       nan        |           nan        |                 nan        |       nan        |               nan        |          nan        |         nan        |         nan        |      nan        |              nan        |                       nan        |         nan        | nan                |
| P3         | unconfigured: initial risk budget required                     |   nan        |         nan        |        nan        |          nan        |       nan        |       nan        |           nan        |                 nan        |       nan        |               nan        |          nan        |         nan        |         nan        |      nan        |              nan        |                       nan        |         nan        | nan                |
| P4         | configured                                                     | 10000.000000 |           0.000000 |          0.072689 |            0.067905 |        -0.108210 |         0.271420 |             0.039005 |                   0.615400 |         0.272000 |                -0.148472 |           -0.080324 |          -0.161433 |          -0.030562 |        3.055880 |          1047133.051894 |                    536851.757930 |      532601.972140 | all scenarios      |
| P5         | configured                                                     | 10000.000000 |           0.000000 |          0.072803 |            0.068165 |        -0.108000 |         0.270697 |             0.039119 |                   0.617200 |         0.270500 |                -0.148788 |           -0.080299 |          -0.162273 |          -0.030637 |        2.489964 |           754159.491914 |                    536937.837131 |      531164.010936 | all scenarios      |
| P6         | unconfigured: dynamic risk budget required                     |   nan        |         nan        |        nan        |          nan        |       nan        |       nan        |           nan        |                 nan        |       nan        |               nan        |          nan        |         nan        |         nan        |      nan        |              nan        |                       nan        |         nan        | nan                |
| P7         | unconfigured: drawdown threshold and reduction factor required |   nan        |         nan        |        nan        |          nan        |       nan        |       nan        |           nan        |                 nan        |       nan        |               nan        |          nan        |         nan        |         nan        |      nan        |              nan        |                       nan        |         nan        | nan                |

The outperformance frequency is the proportion of scenarios outperforming Fund X under the specified historical sample and simulation assumptions. Execution failures remain explicitly counted, and summary statistics identify any incomplete scenario population.

| comparison                 | status                                                         |   paired_scenarios |   mean_difference |   median_difference |   p05_difference |   p95_difference |   positive_difference_frequency |
|:---------------------------|:---------------------------------------------------------------|-------------------:|------------------:|--------------------:|-----------------:|-----------------:|--------------------------------:|
| rebalancing                | configured                                                     |       10000.000000 |         -0.002320 |           -0.001497 |        -0.021523 |         0.013952 |                        0.430900 |
| initial risk               | unconfigured: initial risk budget required                     |         nan        |        nan        |          nan        |       nan        |       nan        |                      nan        |
| risk portfolio rebalancing | unconfigured: initial risk budget required                     |         nan        |        nan        |          nan        |       nan        |       nan        |                      nan        |
| daily rebalancing          | configured                                                     |       10000.000000 |         -0.002830 |           -0.001713 |        -0.026535 |         0.017224 |                        0.430200 |
| weekly rebalancing         | configured                                                     |       10000.000000 |         -0.002716 |           -0.001389 |        -0.026481 |         0.016917 |                        0.442700 |
| risk-triggered reduction   | unconfigured: dynamic risk budget required                     |         nan        |        nan        |          nan        |       nan        |       nan        |                      nan        |
| loss-triggered reduction   | unconfigured: drawdown threshold and reduction factor required |         nan        |        nan        |          nan        |       nan        |       nan        |                      nan        |

The actual result's percentile uses the same strategy's simulated net-liquidation-return distribution. The simulated market paths start at each asset's last pre-cutoff adjusted close and use the same execution and accounting engine as the historical replay. This preserves an asset-specific unit scale for rounding without using evaluation prices.

## Price and risk simulation paths

![All 12 asset price simulations](figures/asset_price_simulation.svg)

![All 12 asset risk simulations](figures/asset_risk_simulation.svg)

![Portfolio NAV, volatility and drawdown simulations](figures/portfolio_simulation.svg)

The risk model starts from the pre-cutoff Ledoit–Wolf covariance. After each completed simulated return, it updates the annualized zero-mean second moment using EWMA decay 0.94. Every portfolio uses its own signed, drifting holdings and NAV with that scenario's covariance to calculate estimated volatility. This decay is a declared modelling assumption. Estimated volatility is derived from price history; the joint bootstrap supplies the stochastic price paths.

A decision at observation t uses covariance, prices, holdings, NAV and drawdown through t−1. Day 2 therefore uses day 1 information. Weekly execution at observation 6 uses the five observed closing levels through observation 5; those five levels contain four new return intervals. Earlier training history initializes risk. The terminal date suppresses new rebalancing.

Shaded areas show pointwise 5th–95th percentiles across all 10,000 scenarios; their boundaries are not individual tradable paths. Thin lines show predefined scenario IDs 0–4. NAV and risk bands are marked-to-market diagnostics; terminal-return tables include hypothetical liquidation. Failure counts are retained, and portfolio bands are suppressed if any financing outcome is undefined.

## Published baseline reconciliation

| measure                |   published |   standardized |
|:-----------------------|------------:|---------------:|
| gross_return           | 0.045893642 |    0.045893642 |
| net_liquidation_return | 0.042808394 |    0.042756192 |

The published baseline charges 2% annual borrow on initial short exposure over trading intervals divided by 252. The standardized ledger charges 2% annual borrow on the preceding day's outstanding short market value over elapsed calendar days divided by 365. Initial fees use original capital, and exit fees use actual ending notional. Both retain zero cash interest. The gross P0 path and the daily-rebalanced Fund X definition reproduce the saved baseline.

## Benchmark and financing

Fund X is a daily-rebalanced proxy benchmark with 20% `^SPGSCI`, 50% `URTH`, and 30% `BNDW`. Its index and ETF returns are compounded daily. B0 has no assumed portfolio transaction fees: it is a reference index calculation. `^SPGSCI` is an index observation. Benchmark turnover and costs of zero are placeholders for the reference calculation; an executable implementation requires instruments, spreads, and fees.

The cash account includes signed short proceeds. Current short market value is restricted as collateral; available cash is cash minus restricted collateral. The engine rejects unavailable financing and invalid prices. Borrow availability, initial margin in excess of 100% short market value, market impact, taxes, and execution capacity at $500 million remain unverified. The 2% borrow rate and 10-basis-point trading fee are illustrative assumptions.

## Data and research limits

- The original stock training data is derived from synthetic_prices.csv. Its provenance, survivorship coverage, and corporate-action conventions remain independently unverified.

- The cached evaluation prices were downloaded by the original analysis with yfinance auto_adjust=True. Stock, URTH, and BNDW levels therefore represent dividend/split-adjusted return proxies. Exact cached corporate-action adjustments have not been independently reconciled. https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html

- ^SPGSCI is the S&P GSCI price/spot index series; the separate total-return series is ^SPGSCITR. It omits the total-return variant collateral yield. Fund X mixes this price index with ETF adjusted-return proxies and is not an independently verified tradable fund. https://finance.yahoo.com/quote/%5ESPGSCI/ ; https://finance.yahoo.com/quote/%5ESPGSCITR/

- Opening fills, action-level dividends, split events, halts, delistings, and borrow availability are unavailable in the cached evaluation panel. Adjusted-close synthetic-unit accounting includes short dividend effects through signed adjusted returns; separate dividend cash flows are not added.

- The initial allocation uses fractional synthetic units; subsequent monthly quantity changes are rounded to the nearest whole synthetic unit. These adjusted units cannot be interpreted as exchange-executable shares.

- Missing or nonpositive prices cause a hard failure. No backfilling or assumed missing-price fills occur. Insufficient collateral cash or nonpositive NAV rejects a scenario and is explicitly counted.

- Benchmark pre-cutoff adjusted prices were fetched separately from Yahoo Finance and are archived with hashes. The joint panel combines this source with the original stock training panel. Source revisions and convention differences can affect the result.

- The initial risk budget is unconfigured by default. P2/P3 remain visible as unconfigured relaxed-exposure variants. Dynamic volatility and drawdown triggers P6/P7 also require explicit thresholds and responses. Their supported engines are exercised by tests; configured production strategies are reported consistently.

- Daily and five-session policies use previous-close information. Evolving EWMA risk is estimated from each path independently with pre-cutoff covariance initialization; the 0.94 decay is a declared assumption. Price and risk bands summarize pointwise scenario distributions.

- The 2026 evaluation period has been explored before this implementation. This is a historical diagnostic comparison, with illustrative costs and financing constraints.

The evaluation period had already been explored during research. These are historical diagnostic comparisons. Code-level cutoff enforcement preserves computational causality; it cannot remove prior researcher knowledge. The original analysis, forecasts, notebooks, and outputs are retained separately.
