# Portfolio rebalancing and initial risk positioning

This historical diagnostic compares the frozen momentum portfolio with monthly fixed-target rebalancing. Starting equity is $500,000,000. Entry uses the 1 May 2026 adjusted close; the endpoint uses the 3 August 2026 adjusted close. There are 64 valuation observations and 63 close-to-close return intervals on the fixed XNYS calendar.

The monthly execution dates are 2026-06-01, 2026-07-01. Orders use the preceding session's prices and NAV. Fixed quantities fill at the next scheduled adjusted close. The first portfolio allocation is a same-close idealization. Fractional quantities represent synthetic dividend-adjusted units. These results are idealized close-price diagnostics. Verified opening execution requires a separate coherent open, close, split, and dividend dataset.

## Historical comparison

Primary net returns include entry, actual rebalance trades, daily outstanding-short borrowing, and hypothetical terminal liquidation costs. Marked-to-market returns retain the open positions. Gross returns use a parallel zero-cost ledger with its own causal NAV sizing.

| strategy   | status                             |   net_return |   max_drawdown |   realized_volatility |   gross_return |   mtm_net_return |   excess_return |   tracking_error |   turnover |   transaction_cost |   terminal_liquidation_cost |   borrow_cost |   simulation_percentile |
|:-----------|:-----------------------------------|-------------:|---------------:|----------------------:|---------------:|-----------------:|----------------:|-----------------:|-----------:|-------------------:|----------------------------:|--------------:|------------------------:|
| B0         | proxy benchmark                    |     0.002294 |      -0.045120 |              0.077475 |       0.002294 |         0.002294 |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |               20.040000 |
| P0         | historical close-price diagnostic  |     0.042756 |      -0.089073 |              0.286604 |       0.045894 |         0.043841 |        0.040462 |         0.251930 |   2.039668 |      500000.000000 |               542624.233847 | 526100.776027 |               41.010000 |
| P1         | historical close-price diagnostic  |     0.078810 |      -0.063309 |              0.255826 |       0.082282 |         0.079894 |        0.076516 |         0.226919 |   2.259007 |      634752.715415 |               542034.741420 | 522616.349748 |               53.450000 |
| P2         | unconfigured: risk budget required |   nan        |     nan        |            nan        |     nan        |       nan        |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |              nan        |
| P3         | unconfigured: risk budget required |   nan        |     nan        |            nan        |     nan        |       nan        |      nan        |       nan        | nan        |         nan        |                  nan        |    nan        |              nan        |

![Historical NAV](figures/historical_nav.svg)

P2 and P3 are relaxed-exposure variants. Their default status is unconfigured because no independently justified volatility budget has been supplied. The pipeline supports a positive predeclared `risk_budget` in the configuration; it freezes the scale before simulation and historical replay. All five predefined strategy IDs remain visible in the output tables.

## Paired historical-bootstrap scenarios

The joint bootstrap draws 10,000 scenarios with seed 20260428, using contiguous blocks of 13 daily return observations. Each asset and each strategy receives the same sampled historical dates. The frozen policy records the pre-cutoff block-length rule. This is a historical-resampling forecast and does not establish predictive momentum excess returns.

| strategy   | status                             |    scenarios |   failed_scenarios |   mean_net_return |   median_net_return |   p05_net_return |   p95_net_return |   mean_excess_return |   outperformance_frequency |   loss_frequency |   worst_5pct_mean_return |   mean_max_drawdown |   p05_max_drawdown |   p95_max_drawdown |   mean_turnover |   mean_transaction_cost |   mean_terminal_liquidation_cost |   mean_borrow_cost | statistics_basis   |
|:-----------|:-----------------------------------|-------------:|-------------------:|------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|-----------------:|-------------------------:|--------------------:|-------------------:|-------------------:|----------------:|------------------------:|---------------------------------:|-------------------:|:-------------------|
| B0         | configured                         | 10000.000000 |           0.000000 |          0.033684 |            0.035342 |        -0.035172 |         0.096218 |             0.000000 |                   0.000000 |         0.186200 |                -0.056331 |           -0.036078 |          -0.086904 |          -0.012567 |        0.000000 |                0.000000 |                       nan        |           0.000000 | all scenarios      |
| P0         | configured                         | 10000.000000 |           0.000000 |          0.075519 |            0.071375 |        -0.108123 |         0.279991 |             0.041835 |                   0.626800 |         0.271200 |                -0.148028 |           -0.081017 |          -0.162530 |          -0.031408 |        1.995280 |           500000.000000 |                    535235.533631 |      509642.697065 | all scenarios      |
| P1         | configured                         | 10000.000000 |           0.000000 |          0.073200 |            0.068518 |        -0.107349 |         0.271599 |             0.039515 |                   0.619700 |         0.272400 |                -0.148294 |           -0.080398 |          -0.161810 |          -0.030797 |        2.166441 |           587588.988885 |                    535724.991525 |      524962.191517 | all scenarios      |
| P2         | unconfigured: risk budget required |   nan        |         nan        |        nan        |          nan        |       nan        |       nan        |           nan        |                 nan        |       nan        |               nan        |          nan        |         nan        |         nan        |      nan        |              nan        |                       nan        |         nan        | nan                |
| P3         | unconfigured: risk budget required |   nan        |         nan        |        nan        |          nan        |       nan        |       nan        |           nan        |                 nan        |       nan        |               nan        |          nan        |         nan        |         nan        |      nan        |              nan        |                       nan        |         nan        | nan                |

The outperformance frequency is the proportion of scenarios outperforming Fund X under the specified historical sample and simulation assumptions. Execution failures remain explicitly counted, and summary statistics identify any incomplete scenario population.

| comparison                 | status                             |   paired_scenarios |   mean_difference |   median_difference |   p05_difference |   p95_difference |   positive_difference_frequency |
|:---------------------------|:-----------------------------------|-------------------:|------------------:|--------------------:|-----------------:|-----------------:|--------------------------------:|
| rebalancing                | configured                         |       10000.000000 |         -0.002320 |           -0.001497 |        -0.021523 |         0.013952 |                        0.430900 |
| initial risk               | unconfigured: risk budget required |         nan        |        nan        |          nan        |       nan        |       nan        |                      nan        |
| risk portfolio rebalancing | unconfigured: risk budget required |         nan        |        nan        |          nan        |       nan        |       nan        |                      nan        |

The actual result's percentile uses the same strategy's simulated net-liquidation-return distribution. The simulated market paths start at each asset's last pre-cutoff adjusted close and use the same execution and accounting engine as the historical replay. This preserves an asset-specific unit scale for rounding without using evaluation prices.

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

- The risk budget is unconfigured by default. P2/P3 remain visible as unconfigured relaxed-exposure variants. The pre-cutoff diagnostics support choosing a budget in a separate prospective research decision.

- The 2026 evaluation period has been explored before this implementation. This is a historical diagnostic comparison, with illustrative costs and financing constraints.

The evaluation period had already been explored during research. These are historical diagnostic comparisons. Code-level cutoff enforcement preserves computational causality; it cannot remove prior researcher knowledge. The original analysis, forecasts, notebooks, and outputs are retained separately.
