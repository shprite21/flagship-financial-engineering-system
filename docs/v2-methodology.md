# Q V2 methodology and numerical changes

The main demonstration is reproducible strategy research with explicit failure states. It is not a certification of profitability. Detailed formulas and prerequisites are in [Strategy Survival](strategy-survival.md), [statistical audit](audit-statistics.md) and [accounting audit](audit-accounting.md).

## Accounting and time

The Portfolio Research path generates causal target weights and uses the drifting fractional backtester. A signal at completed bar t is lagged before exposure affects subsequent close-to-close returns. This is a return proxy; it is not proof of a next-open fill. Commission/slippage are charged on executed changes against drifted holdings, and shorts incur the configured borrow assumption. Whole shares, cash feasibility, volume caps and delayed next-close fills are checked in a separate Survival stress account. The strict daily and prospective paper accounts retain their separate conventions.

Constant-weight mode restores the scheduled target fractions every observation, including between target-update dates. Turnover compares each target with prior end weights after price moves, fees and borrow: `sum(abs(w_target - w_previous_end))`, where `w_end = w_target * (1 + asset_return) / (1 + net_return)`. This charges daily restoration trades even when targets are unchanged. Sizing uses pre-cost NAV with implicit cash/financing; it remains a fractional close-to-close proxy without whole-share, cash-feasibility or settlement enforcement. The default research workspace uses the separate drifting mode.

Annualization is 252 daily observations by default, with sample standard deviation and zero cash hurdle. Undefined Sharpe, Sortino and Calmar ratios are unavailable, not zero. Sortino uses the lower partial RMS over all observations, with positive excess returns contributing zero. Starting NAV enters drawdown, including a loss on the first observation. Exhausted accounts cannot mathematically recover after a return at or below -100%.

Allocation bounds are applied after normalization and regime scaling. Unallocated long-only budget remains cash when position caps prevent full investment. Optimizer fallback weights must satisfy the same bounds, sector and budget constraints; an infeasible solution raises an error.

## Data and selection

Snapshots contain the exact prices, benchmark, request and source archive. Reusing a saved dataset now verifies its combined SHA-256 before parsing those same bytes. Benchmarks must have unique, ordered, aligned positive finite closes; missing observations cannot become zero benchmark returns.

Asset returns/momentum preserve missing prices. Auxiliary macro/sector branches still require separate lag/gap review. Selected constituents are not historical point-in-time membership. Adjusted data does not by itself establish corporate-action, dividend, volume-unit or calendar correctness.

Chronological train/validation/test segments and complete walk-forward windows preserve temporal order. The main catalogue uses fixed rules, not parameter refitting inside every fold. Previously examined historical data remains retrospective. Local parameter sensitivity is diagnostic; the representative protocol does not choose its best-performing neighbor.

## Inference

- **HAC:** intercept-only OLS with Bartlett/Newey-West covariance, configurable bandwidth, normal asymptotic inference and a one-sided mean-return null. Dependence does not disappear merely because a p-value is computed.
- **Bootstrap:** seeded circular moving blocks preserve short-range dependence within sampled blocks. Percentile intervals assume approximate stationarity and do not generate unseen tails.
- **BY:** the harmonic Benjamini-Yekutieli adjustment covers the recorded compatible p-value family. Missing external trials and adaptive research remain limitations.
- **DSR:** daily Sharpe, cross-trial Sharpe dispersion, skew and Pearson kurtosis enter the expected-maximum/PSR formula. Effective independent trials and IID-return assumptions must be explicitly supplied; the demo leaves DSR unavailable.
- **CSCV/PBO:** exact complementary half-block partitions rank in-sample winners out of sample. Tied winners share each partition's mass; exported logits have explicit weights. Candidate order therefore cannot choose a favorable tie winner. No binomial confidence interval is assigned to dependent partitions.
- **Regimes:** the generic HMM now forward-filters, but scaling/model fitting must still use training data only. Each prediction call resets its prior. The main research workspace uses causal rule regimes; its HMM Survival attachment is not supplied automatically.

Required layers, integrity and FAIL-severity gates remain unresolved when metrics or calculations are absent/nonfinite. There is no score. WARN requires interpretation even when configured research gates are satisfied. Paper promotion also requires the original mandate gates; synthetic research remains blocked.

## Reproducibility boundary

Existing results are preserved; fixes apply to new runs with different source fingerprints. Survival protocol version 1.1.0 includes the corrected tie/gate behavior. Exact replay checks local source, dependency versions, input/trial hashes and deterministic outputs. Different BLAS/platform versions can fail bitwise equality; no hidden tolerance masks that failure.

Paper registration freezes a protocol and allows only subsequent evidence. A registration with zero observations is not a track record. The automated paper service is a simulation and requires an explicit feed; broker-backed fills and production live execution remain outside the verified core.

See [verification](verification.md) and the [fixed experiment](representative-experiment.md) for executed evidence.

