# Q accounting, allocation and causal-input audit

Source inspection: 2026-10-04; constant-weight cost follow-up: 2026-10-05, `C:\quant\terminal-v2` only. This documents saved V2 fixes and the boundaries of the inspected Python portfolio path. It does not claim equivalence with the terminal, strict daily, bar-lab or prospective paper engines. See [implementation](implementation.md), [workflow/accounting conventions](flagship.md), [data conventions](real-market-data.md) and [statistical audit](audit-statistics.md).

## Portfolio return accounting

[backtesting/engine.py](../apps/engine/backtesting/engine.py), `BacktestConfig.__post_init__`, rejects nonpositive/nonfinite capital, invalid costs and execution lags below one, including booleans and fractional lags. `VectorizedBacktester.run` requires nonempty, unique, chronological, finite positive prices. It rejects duplicate target axes and infinite targets; missing target cells explicitly mean zero allocation. Returns use `pct_change(fill_method=None)`, with only the initial price observation converted to a zero return after price validation.

Both modes apply lagged weights to close-to-close asset returns and subtract modeled costs before compounding. A lag of one means a target at completed bar `t` contributes to the following observed return interval. This is a fractional return proxy, not evidence that an order filled at the next open or at a known closing auction price. `allow_short=False` clips negative targets; gross leverage and cash feasibility belong to the allocator/mandate, not a whole-share cash ledger in this class.

| Mode / function | Accounting behavior | Important boundary |
| --- | --- | --- |
| `run`, `drift_between_rebalances=False` | Scheduled target fractions are forward-held and lagged. Every observation restores those fractions against prior actual end weights, charging traded notional including price drift and the effect of prior fees/borrow on NAV. | Target updates and trading frequency differ: even weekly targets require daily restoration. Sizing uses pre-cost NAV with implicit cash/financing, not whole-share or funded-account constraints. |
| `_run_drifting` | Rebalances only on scheduled lagged decisions; between them, holdings drift. Turnover is the absolute difference between new targets and prior end-of-period weights. End weights are `w_start * (1 + asset_return) / (1 + net_portfolio_return)`. | Fractional holdings and implicit cash/financing remain. Weekly/monthly decisions use observed period boundaries; a partial final period is not automatically a scheduled close. No production exchange calendar or executable quote is established by this scheduling. |
| `BacktestResult.summary` | Adds the explicit initial-capital point before aggregate metrics. | Saved results retain their own conventions; new analytics must not overwrite historical snapshots. |

Both branches now reject nonfinite net returns or a period return at or below -100%, before an exhausted account can later appear to recover through multiplication. Linear transaction drag is traded notional fraction times bps/10,000; short borrow uses held short exposure times annual bps/10,000/252. [risk/costs.py](../apps/engine/risk/costs.py), `TransactionCostModel.as_return_drag` and `SlippageModel.estimate`, supply linear fixed slippage and an optional lagged-volatility component. These are modeled assumptions, not calibrated impact, financing, borrow availability, tax or settlement services.

The follow-up reproduced the former constant-weight undercharge in four independent dollar-ledger cases: long-only and long/short portfolios with daily and weekly target updates. The corrected NAV, commission/borrow, slippage and turnover reconcile to explicit fractional shares plus cash; a fully invested single asset with zero costs requires no restoration turnover. Existing future-price perturbation and bankruptcy checks still apply to both modes. Historical results keep their original source snapshots; this correction applies to new runs.

## Saved metric and report fixes

[analytics/metrics.py](../apps/engine/analytics/metrics.py) implements the following conventions:

- `sharpe_ratio` uses sample standard deviation and returns NaN when its denominator is undefined or zero. The risk-free input is an annual arithmetic rate divided by the annualization factor; the default is zero.
- `sortino_ratio` uses the lower partial RMS over **all** observed excess returns: `sqrt(mean(min(excess, 0)^2))`. Positive returns contribute zero to the downside moment. No observed downside produces NaN, not zero or infinity.
- `drawdown_series` and `max_drawdown` accept initial NAV as a lower bound on the running peak. `aggregate_metrics`, `calmar_ratio` and `_initial_equity` preserve the first loss relative to starting capital. An explicitly supplied extra initial NAV point is supported; otherwise baseline reconstruction uses first marked NAV divided by `1 + first_return`.
- `calmar_ratio` is unavailable when drawdown is zero; `rolling_sharpe` leaves zero-volatility windows unavailable. Empty aggregate results retain zero descriptive totals but unavailable ratios.

General analytics helpers drop missing returns. The Survival statistical boundary instead rejects missing/nonfinite returns. Do not infer global data validation from the metric helpers, and supply correctly aligned NAV and return paths. Baseline reconstruction cannot recover a positive pre-return NAV from a first return at or below -100%; the backtester explicitly supplies initial capital and rejects such insolvency paths.

[analytics/tearsheet.py](../apps/engine/analytics/tearsheet.py), `PerformanceReport.from_backtest`, now copies `result.turnover` and uses initial capital for drawdown. It no longer mistakes passive drift in holdings for executed trading. The general `metrics.turnover` helper still measures weight differences and should not replace the execution ledger's turnover in a drifting report.

## Allocation bounds and residual cash

[portfolio/allocation.py](../apps/engine/portfolio/allocation.py) validates finite leverage/bounds/risk settings and rejects incompatible constraints. `InverseVolatilityAllocator.allocate`, `RollingSharpeAllocator.allocate` and `RegimeConditionedAllocator.allocate` normalize scores, apply bounds, then check the gross ceiling; they do not renormalize clipped positions upward and undo the cap. Regime scaling is bounded again after scaling. A single asset capped at 15% can therefore leave 85% unallocated in an unlevered long-only account.

`RiskParityAllocator._solve`, `ConstrainedOptimizer._long_budget` and `_capped_budget` use the feasible long budget `min(gross_leverage, asset_count * max_weight)` and reject unfundable minimum weights. Risk parity has a feasible bounded fallback when optimization is unavailable or fails. `ConstrainedOptimizer` applies long-only nonnegativity even if the configured lower bound is negative, checks finite weights, bounds, gross budget and sector constraints after solver output, and applies the same constraints to fallbacks. A solution that cannot satisfy them raises rather than silently increasing exposure.

This establishes constraint handling, not estimator accuracy or global optimizer convergence. Rolling means/covariances remain sample estimates; covariance handling can fill unavailable entries with zero. Residual weight is an implicit cash/financing convention, not a settlement-aware funded account. There is no universal requirement that all available budget be invested.

## Data gaps and regime causality

[data/models.py](../apps/engine/data/models.py), `MarketDataBundle.returns`, and the asset return/momentum branches of [data/features.py](../apps/engine/data/features.py), `FeatureEngineer.build`, disable implicit price filling. `align_frames` defaults to preserving missing observations; explicitly requested forward fill leaves volume missing, and backward fill is rejected. A valuation carry-forward is not an executable bar. Benchmark, sector, volatility and macro feature branches still contain explicit forward fills, and some auxiliary `pct_change` calls retain default filling. Those paths require separate timing/gap review; the saved fix is not a whole-library point-in-time data guarantee.

[regime_detection/hmm.py](../apps/engine/regime_detection/hmm.py), `_filtered_probabilities`, now implements log-space forward Bayes recursion using fitted start probabilities, transition matrix and emission likelihoods. Labels use filtered-probability argmax, avoiding Viterbi paths and backward-smoothed probabilities. The independent-observation mixture/quantile fallbacks are identified by backend and probability method; they are not HMM transition models.

`fit` records the training interval and fits scaling, model parameters and state ordering on its supplied rows. `predict` reports overlap with training, and state ordering includes unobserved states so probability columns map bijectively. `_prepare_features` rejects unordered/duplicate indices and drops rows with missing/nonfinite numeric features. Each prediction call restarts at the fitted initial distribution; it does not carry an online posterior between calls. Removed rows also compress the sequence rather than model elapsed-session transitions.

**Train-only fitting remains a caller responsibility.** `BaseRegimeDetector.fit_predict` in [regime_detection/base.py](../apps/engine/regime_detection/base.py) fits and predicts the same supplied sample. Forward filtering cannot remove leakage already introduced by full-sample scaling, fitting or state ordering. Survival's `pipeline.regimes` requires a declared `train_only_forward_filter` provenance path and lags accepted labels; that declaration does not independently verify training inputs. The state-ordering magnitude proxy does not establish universally meaningful economic regimes.

## Separate whole-share stress and unresolved scope

[research/survival/execution.py](../apps/engine/research/survival/execution.py), `execution_stress`, is a separate unlevered long-only stress ledger: signal-time integer share targets, delayed next-close fills, prior 20-bar volume participation caps, sells before buys, cash checks, and expiring unfilled remainder. It requires complete nonnegative volume and rejects unsupported short/leverage mandates. It does not convert the fractional portfolio engine into this account. Adjusted price/volume units and indicative capacity remain approximations, without short locate, corporate-action/settlement completeness or a calibrated impact curve.

Selected universes lack historical point-in-time constituents and complete delisted coverage. Provider adjustment units differ. Keep these limitations visible and compare engine outputs only after reconciling timing, dividends, currency, price basis, sizing and costs. Live execution remains disabled; research gates and successful accounting tests do not supply missing production risk, compliance, settlement, reconciliation or approval services.

## Regression evidence and resuming

[tests/test_accounting_integrity.py](../apps/engine/tests/test_accounting_integrity.py) contains numerical/invariant checks for the downside moment, unavailable ratios, first-loss baseline, drifting holdings versus an explicit cash-plus-shares reference, executed turnover, lag and future perturbation, invalid prices/lags, bankruptcy, missing observations/volume, cap-preserving allocators and optimizer fallback, long-only bounds, and HMM probabilities versus an independent Bayes recursion. The HMM fixture explicitly rejects use of Viterbi or smoothed predictions.

This page records inspected test coverage, not an executed result. On resume, record focused and full-suite outcomes in the audit run ledger, including required web quant tests, TypeScript checking and the application build. Investigate remaining auxiliary data fills and caller-level train/test isolation separately; retain fractional and whole-share accounting labels in reports and preserve all historical strategy/result snapshots.

## Executed verification
The original focused statistical/accounting/provenance batch passed 54 cases. The follow-up added five constant-weight cases; the complete configured Python suite now passes 309 cases, including all 59 in that group. See [verification](verification.md) for commands, scope, the deterministic clock fixture and warnings.
