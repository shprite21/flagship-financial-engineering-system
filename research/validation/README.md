# Historical strategy validation

The regime allocator lost **0.85% annualized after costs** on six US equities. Its Sharpe exceeded the equal-budget baseline by 0.36, but the paired confidence interval includes zero. The KO/PEP cointegration study found no eligible spread in ten outer windows. These results leave both proposed edges unconfirmed.

## Out-of-sample results

January 4, 2021 through December 31, 2025 covers 1,255 common US sessions. Both experiments start with 504 calibration sessions from January 3, 2019 through December 31, 2020. All figures below include a modeled 2 bp commission and 3 bp adverse slippage per traded dollar, plus 3% annualized short borrow. Uninvested cash earns zero.

| Module and policy | Net Sharpe | CAGR | Maximum drawdown | Annual turnover | Total return |
| --- | ---: | ---: | ---: | ---: | ---: |
| Regime, static equal sleeve budgets | −0.50 | −2.21% | −15.86% | 26.96× | −10.51% |
| Regime, HMM-weighted sleeves | −0.14 | −0.85% | −11.99% | 25.99× | −4.16% |
| KO/PEP, fixed spread rule | Undefined | 0.00% | 0.00% | 0.00× | 0.00% |
| KO/PEP, nested parameter selection | Undefined | 0.00% | 0.00% | 0.00× | 0.00% |

Annual turnover sums buys and sells at the reference close, divides each session's notional by prior equity, and multiplies the daily mean by 252. It includes turnover between sleeves that can offset at the account level. Sharpe uses the arithmetic mean daily return divided by its sample standard deviation, annualized by √252 with a zero risk-free rate. CAGR compounds the OOS path on a 252-session year. Drawdown includes inception equity and measures the largest peak-to-trough decline.

## Regime allocation

**Hypothesis.** Forward-filtered HMM probabilities improve net Sharpe over static one-third budgets for the same momentum, mean-reversion and statistical-arbitrage signals. The universe uses the first name in each of the source study's six sector lists, yielding KO, XOM, JPM, MSFT, JNJ and WMT. No cross-sectional selection used the results of this run.

The existing module fits a three-state full-covariance Gaussian HMM to market return, volatility and trend features. It fits scalers and parameters through each formation close, refits every 126 sessions, and filters subsequent observations forward. A training-only Johansen test admitted the basket sleeve at 3 of 10 refits. Both allocators use the same execution lag, constraints, gross headroom and 100,000 USD initial equity. All ten fits finished within the engine's absolute log-likelihood-change tolerance of 0.0001. Two fits had small negative terminal changes, preserved in the diagnostics. [Regime implementation](../../apps/engine/qresearch/regimes.py) · [Shared account](../../apps/engine/qresearch/equity_account.py)

The observed Sharpe difference was **+0.36**, with a paired 97.5% circular-block bootstrap interval of **[−0.15, +0.86]**. The interval uses 3,999 resamples of 20 consecutive sessions and a Bonferroni adjustment for two specified comparisons. Intervals using 5- and 60-session blocks were [−0.13, +0.89] and [−0.14, +0.94]. Inference conditions on these fitted rules, realized universe and sample. It omits uncertainty from choosing the research design or refitting on alternative histories.

| Candidate HMM | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Net calendar-year return | −0.94% | −2.98% | −5.41% | +2.68% | +2.68% |

### What execution costs changed

Each row reruns fitting, selection, target generation and account execution. Short borrow remains 3% in every case. Fees and slippage scale together. Whole-share quantities can change as the account value changes.

| One-way commission + slippage | Baseline Sharpe | HMM Sharpe | HMM CAGR | HMM maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| 0 + 0 bp | −0.18 | +0.12 | +0.47% | −9.77% |
| 2 + 3 bp | −0.50 | −0.14 | −0.85% | −11.99% |
| 4 + 6 bp | −0.82 | −0.39 | −2.11% | −16.07% |

At the base rate the HMM generated fills on 1,243 sessions. Commission and slippage consumed 1.30% of prior equity per year on an arithmetic basis, and borrow consumed 0.77%. A second attribution holds the base-case accepted quantities fixed and refunds or doubles their realized execution charges. Its 0/5/10 bp Sharpe values are +0.11, −0.14 and −0.39.

## Cointegration

**Hypothesis.** Training-selected hedge weights, lookback and thresholds improve KO/PEP spread-trading Sharpe relative to fixed 20-session lookback, 2.0-entry and 0.5-exit z-score thresholds. KO and PEP are the first two named constituents of the existing staples group, with similar businesses.

Each outer window uses 504 prior sessions, including 126 validation sessions, followed by up to 126 test sessions. The Engle–Granger gate admits a pair at a nominal 5% threshold. The module reserves up to 24 seeded Optuna trials per eligible inner window and refits the hedge on the full outer training window before testing. No inner window qualified for optimization. The ten outer p-values ranged from 0.217 to 0.939. Both policies therefore stayed in cash in every window. Their return volatility, trading costs and turnover were zero. Sharpe and the difference in Sharpe are undefined. The output records each rejected fold. [Cointegration implementation](../../apps/engine/qresearch/cointegration.py) · [Nested walk-forward implementation](../../apps/engine/qresearch/basket.py) · [Fold diagnostics](results/folds.json)

## Data and execution assumptions

The private research snapshot contains Yahoo Finance daily adjusted closes retrieved on November 7, 2026. The source manifest records provider request parameters and original response hashes. The runner checks the processed panel's digest against both that manifest and the study protocol. Reviewers can independently recompute performance from the committed derived daily ledger. Full price-to-result replay requires the matching private snapshot. No vendor price series is included here.

The surviving universe and retrospectively adjusted histories introduce selection and revision bias. The test dates were already historical when the protocol was written. Daily adjusted prices proxy total returns. Next-close execution, available borrow, linear slippage and collateral are simulation assumptions. The HMM book marks open final holdings to market. Each cointegration fold starts from fresh capital and schedules a final liquidation. Dividends and corporate actions enter through adjusted prices. The calculations omit taxes, interest on cash and liquidity-dependent market impact.

## Reproduction

From the repository root, use the Python environment specified by the engine's locked dependencies. Supply the existing private price panel and its sibling source manifest. An alternative output directory preserves the reference artifacts during replay. [Engine dependency lock](../../apps/engine/requirements.lock.txt)

```powershell
python research/validation/run.py --snapshot "C:/quant/paper/data/processed/adj_close.csv" --manifest "C:/quant/paper/data/manifest.json" --output "$env:TEMP/flagship-validation-replay"
python research/validation/verify.py --results "$env:TEMP/flagship-validation-replay"
```

To verify the committed protocol, engine fingerprints, fold chronology and aggregate metrics from the supplied daily returns, any standard Python 3.9+ installation can run the following command offline. This reports four matched ledgers on 1,255 sessions and five cost treatments.

```text
python research/validation/verify.py
```

The parameter file records both hypotheses and selection rules. The machine-readable report includes library versions, input provenance, source and evidence hashes, calendar-year returns and bootstrap results. The daily CSV records returns, realized turnover, execution charges and borrow charges for every session. [Protocol](protocol.json) · [Study runner](run.py) · [Independent verifier](verify.py) · [Full metrics](results/summary.json) · [Daily OOS ledger](results/daily.csv)
