# Data quality and execution assumptions

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