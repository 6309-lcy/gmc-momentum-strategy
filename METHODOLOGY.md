# GMC: a historically validated stock-selection strategy

## Investment objective

I construct a long/short stock portfolio using historical information available before 1 May 2026. The initial long positions plus the absolute short positions total **$500 million**. I also assume $500 million starting equity for return and P&L reporting.

The portfolio uses company stocks only. Every selected position has an absolute weight between **5% and 15%**. Long positions total 80% ($400 million), and short positions total 20% ($100 million). Initial net exposure is therefore 60% ($300 million). The remaining cash balance, including short-sale proceeds, is $200 million and earns zero in the model. Gross exposure drifts after entry as prices change.

This strategy seeks a repeatable historical selection rule. It does not claim to identify the portfolio with the highest possible future return.

## Historical information and selection rules

The final allocation uses prices from **29 April 2024 to 28 April 2026**. Earlier history supports chronological validation, with only the preceding two years used at each historical decision date. ETF holdings are excluded through an explicit operating-company allowlist.

At each decision date, I require at least 98% daily return coverage, positive prices, and no daily absolute return above 40% within the training window. This filter is a basic data-quality check. Isolated missing price levels are forward-filled using past information; missing returns in risk estimation are treated as zero. The underlying file is named `synthetic_prices.csv`, and its source and corporate-action adjustments have not been independently verified.

I compare three rules:

1. Momentum alone.
2. Momentum combined with price stability.
3. Momentum and stability with a small Ukraine Phase 2 adjustment.

The momentum score combines:

| Component | Weight in momentum score |
|---|---:|
| Twelve-month momentum, excluding the latest 21 sessions | 35% |
| Six-month momentum, excluding the latest 21 sessions | 30% |
| Recent three-month momentum | 15% |
| Six-month momentum relative to the sector median | 20% |

Each component is converted into a cross-sectional rank score. This limits the influence of extreme raw returns. The stability score rewards lower recent volatility and downside variation. Its candidate rule uses 80% momentum and 20% stability. The analogy candidate gives 10% weight to the observed 2022 Phase 2 rank score and 90% to the momentum/stability combination.

The analogy is used only after its August 2022 observation date. It supplies a historical adjustment rather than a guaranteed conflict pattern.

## Portfolio construction

I select eight long candidates from the highest scores and four short candidates from the lowest scores. At most four candidates can come from the same sector across both books. Each sector's final gross allocation is capped at **45%**.

I translate scores into cautious annual expected-return inputs using:

`expected return = 6% + 8% × score`

This scale is a modelling assumption rather than an independently calibrated forecast. Ledoit–Wolf shrinkage estimates annual covariance from the historical return sample.

The allocation maximises expected return minus a risk penalty times variance and a small concentration penalty. I compare risk penalties of 2, 10, and 20. Because four short holdings at the 5% minimum exactly fill the 20% short budget, each short is fixed at 5%, while the optimiser allocates the long book.

Risk is controlled through this penalty and the sector limits. **There is no hard 8% volatility ceiling in this strategy.**

## Historical validation and selected strategy

I test the nine rule/penalty combinations across **13 chronological blocks**, each containing 63 daily returns. Each allocation uses only information available at its decision date and then holds its initial units over the next block.

Validation assumes execution costs of 10 basis points at entry and exit and a 2% annual charge on initial short exposure. Costs are illustrative. The selection score is annualised average daily return minus twice annualised return variance.

The highest selection score belongs to **momentum alone with risk penalty 2**. Across 819 validation returns, its modelled net cumulative return is **105.15%**, annualised volatility is **19.11%**, and maximum drawdown is **16.74%**. These figures cover multiple years and should not be read as three-month returns. Because these observations select the strategy, they are not an independent test of the chosen rule.

The stability and analogy rules achieved lower scores. The final strategy therefore uses momentum alone. A frozen strategy file records the rule, constraints, information cutoff, and a hash of the saved weights before later prices are loaded.

Amicus (FOLD) is excluded from final entry because its acquisition completed on 27 April 2026. Its eligibility in earlier validation blocks is retained. Source: [BioMarin acquisition announcement](https://www.prnewswire.com/news-releases/biomarin-completes-acquisition-of-amicus-therapeutics-302754256.html).

## Initial portfolio

| Ticker | Sector | Direction | Weight | Initial position |
|---|---|---|---:|---:|
| EQNR | Energy | Long | 15.00% | $75.00m |
| CAT | Industrials | Long | 15.00% | $75.00m |
| CNQ | Energy | Long | 15.00% | $75.00m |
| VLO | Energy | Long | 10.00% | $50.00m |
| WDC | Technology | Long | 7.54% | $37.69m |
| MRNA | Healthcare | Long | 7.46% | $37.31m |
| MU | Technology | Long | 5.00% | $25.00m |
| HAL | Energy | Long | 5.00% | $25.00m |
| RXRX | Healthcare | Short | −5.00% | −$25.00m |
| ZS | Technology | Short | −5.00% | −$25.00m |
| PRGO | Healthcare | Short | −5.00% | −$25.00m |
| AXON | Industrials | Short | −5.00% | −$25.00m |

Unrounded weights satisfy the gross budget and minimum sizes. Energy uses the full 45% sector allowance, so concentration remains material.

![Historical validation and initial weights](aligned_method/validated_strategy/validation_and_weights.svg)

## Three-month forecast and realised performance

Monte Carlo simulates 10,000 paths over **63 daily return intervals**. It uses the final rank-based expected returns, Ledoit–Wolf covariance, correlated normal daily shocks, fixed initial units and zero-interest cash. The actual comparison runs from **1 May to 3 August 2026**, using 64 price observations.

| Measure | Result |
|---|---:|
| Forecast mean return before costs | +2.52% |
| Forecast median return before costs | +2.04% |
| Forecast 5th–95th percentile before costs | −11.74% to +18.47% |
| Forecast mean return after assumed costs | +2.22% |
| Actual return before costs | **+4.59%** |
| Actual return after assumed costs | **+4.28%** |
| Actual P&L before costs | **+$22.95m** |
| Actual P&L after assumed costs | **+$21.40m** |
| Fund X proxy return | +0.23% |
| Actual annualised volatility before costs | 28.61% |
| Actual maximum drawdown before costs | −8.86% |

The portfolio outperformed Fund X during this period, with considerably greater volatility. The forecast stress tests show that halving expected returns and increasing volatility reduce forecast confidence. These stress assumptions are scenarios rather than calibrated probabilities.

![Three-month forecast and diagnostic performance](aligned_method/validated_strategy/forecast_vs_diagnostic.svg)

## Extended realised result through 9 October 2026

I keep the same initial units without rebalancing and extend the review to **9 October 2026**. The period contains **111 daily returns** from the 1 May entry. This extended result is separate from the original three-month forecast.

| Measure | Portfolio before costs | Portfolio after assumed costs | Fund X proxy |
|---|---:|---:|---:|
| Total return | **+34.71%** | **+34.29%** | +2.63% |
| P&L on $500m starting equity | **+$173.56m** | **+$171.43m** | +$13.17m |
| Annualised volatility | 34.32% | 34.36% | 6.66% |
| Maximum drawdown | −9.63% | −9.69% | −4.51% |

The portfolio's before-cost excess return versus Fund X is approximately **32.08 percentage points**, or **$160.39 million** of excess P&L. These figures are modelled holding returns from downloaded adjusted prices, rather than verified broker or fund-account returns.

![NAV, P&L and drawdown through 9 October](aligned_method/validated_strategy/performance_to_9_oct.svg)

![Holding contributions through 9 October](aligned_method/validated_strategy/attribution_to_9_oct.svg)

## Interpretation and limitations

This process improves research discipline by comparing explicit rules chronologically, enforcing position and sector constraints, including illustrative costs, and freezing the allocation before evaluating later prices. It does not establish the best future portfolio.

The stock universe can contain survivorship bias. Historical prices may contain unadjusted corporate actions. Return scaling, sector classifications, the 80/20 long/short split and assumed costs affect the outcome. Actual short availability, liquidity and execution at a $500 million scale have not been verified. Cash interest, taxes and additional financing charges are omitted.

The 2026 period had already been examined during earlier research. It is diagnostic evidence rather than an untouched holdout. High later returns do not remove that limitation. A credible next assessment should preserve the saved rule and use a new period without retrospective changes.

## Files

- [Full executable analysis notebook](GMC_Validated_Strategy.ipynb)
- [Initial portfolio table](aligned_method/validated_strategy/initial_portfolio.csv)
- [Historical validation leaderboard](aligned_method/validated_strategy/validation_leaderboard.csv)
- [Frozen strategy settings](aligned_method/validated_strategy/frozen_strategy.json)
- [Three-month forecast summary](aligned_method/validated_strategy/mc_summary.csv)
- [Three-month diagnostic scorecard](aligned_method/validated_strategy/diagnostic_scorecard.csv)
- [Extended scorecard through 9 October](aligned_method/validated_strategy/scorecard_to_9_oct.csv)
- [Extended holding attribution](aligned_method/validated_strategy/attribution_to_9_oct.csv)
