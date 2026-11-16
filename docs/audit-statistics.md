# Q statistical audit

Source inspection: 2026-10-04, `C:\quant\terminal-v2` only. This records the saved V2 implementation and regression coverage; it does not certify a strategy, establish untouched out-of-sample evidence, or enable execution. Historical results must retain their original code identity and must not be silently recalculated with these changes.

## Implemented calculations

The statistical implementation is [research/survival/statistics.py](../apps/engine/research/survival/statistics.py). [Strategy Survival](strategy-survival.md) describes the surrounding 18-layer workflow; [audit-accounting.md](audit-accounting.md) describes the return paths supplied to it.

| Function | Implemented calculation and prerequisites | Interpretation limit |
| --- | --- | --- |
| `sample`, `metrics` | Finite one-dimensional simple returns strictly above -100%; at least two observations. Geometric total return/CAGR, sample standard deviation (`ddof=1`), annualized Sharpe, and drawdown including initial NAV 1. Sharpe is unavailable for near-zero variance. | Annualization defaults to 252 observations/year and the cash hurdle is zero. This does not validate source data or execution assumptions. |
| `chronological_splits`, `walk_folds` | Disjoint chronological segments; full forward test windows, rolling/expanding training indices, oldest folds retained under the explicit cap. | A chronological split cannot erase prior research exposure to the same history. Fixed rules and trained models require different fitting controls. |
| `block_bootstrap` | Seeded circular moving blocks, truncated to the original sample length; percentile intervals/distributions for Sharpe, CAGR, return and drawdown; fraction of sampled paths losing money. Requires at least `max(minimum, 3 * block_length)` observations and nondegenerate variance. | Assumes approximately stationary, weakly dependent returns. Wraparound is artificial; unseen tails and the full strategy search are absent. Sampled loss frequency is conditional on the historical path. |
| `hac_mean` | Intercept-only OLS with Bartlett/Newey-West covariance, configurable lags, normal critical values, two-sided mean interval and one-sided `H0: mean <= 0` p-value. Requires at least `max(minimum, 2 * lags + 3)` observations and positive long-run variance. | Asymptotic inference needs weak stationarity and finite moments; the selected bandwidth matters. A p-value is not a profitability probability. |
| `fdr` | Benjamini-Yekutieli adjusted p-values in original input order; at least two finite p-values in [0, 1]. | Dependence correction requires valid individual tests and a disclosed family. It cannot recover undisclosed or adaptive trials. |
| `deflated_sharpe` | Daily sample Sharpe; expected maximum Sharpe from cross-trial sample standard deviation, normal quantiles and Euler's constant; PSR denominator uses standardized skew and Pearson kurtosis. | Requires an explicit effective independent trial count between 2 and the observed trial count, nondegenerate return/trial variance, sufficient observations, and an IID-return assumption. A small correlated parameter grid does not identify that count. |
| `pbo` | Exact CSCV over 4-12 even, equal contiguous blocks and all half-block combinations. Discloses discarded trailing rows and rejects invalid, identical or partition-degenerate candidate paths. | Retrospective search diagnostic, not chronological forecasting or a binomial experiment. Small local grids give conditional evidence only. |
| `factor_fit` | OLS on exactly aligned realized factors, intercept and HAC coefficient intervals; two-sided alpha p-value. Requires full rank and at least ten observations per coefficient as well as the configured minimum. | Daily arithmetic alpha is not causal skill. No risk-free subtraction is implicit; realized attribution factors must not become future-informed trading inputs. |

The DSR statistic is `Phi((SR - SR0) * sqrt(T - 1) / sqrt(1 - skew * SR + (PearsonKurtosis - 1) * SR^2 / 4))`. Both `SR` and the cross-trial Sharpe inputs are daily, not annualized. The separate HAC and bootstrap diagnostics address dependence under their own assumptions; they do not transform DSR into a dependence-robust statistic.

## Saved fixes and decision semantics

**CSCV training ties no longer depend on candidate column order.** In `statistics.pbo`, each partition receives mass `1 / binomial(S, S/2)`. If `k` candidates tie for the best training Sharpe, each receives `1/k` of that partition's mass (`rtol=1e-12`, `atol=1e-14`). Complementary-sample Sharpes use average ranks, `w = rank/(N+1)`, and `logit = log(w/(1-w))`. PBO is the sum of weights whose logit is at most zero. Logits are sorted within partitions and accompanied by `logit_weights` and `logit_partitions`. Consumers must use the weights; an unweighted average over the expanded logits overweights tied partitions. Logits are not averaged before applying the loss indicator.

**Unavailable evidence cannot satisfy a required gate.** [research/survival/models.py](../apps/engine/research/survival/models.py), `apply_gates`, accepts only finite numeric metric values, excluding booleans and numeric strings. Missing, NaN and infinite values produce a gate status of `N-A` and JSON-safe `value: null`. A missing gate does not become a measured failure: it remains unresolved.

`models.summarize` always requires integrity layer 1, detects absent required layers and unevaluated configured gates, and blocks `research_gates_satisfied` for unavailable required evidence or any unavailable FAIL-severity gate. Explicit hard failures override inconsistent layer status. A WARN-severity gate on a nonrequired layer may still leave research gates satisfied; WARN remains a review requirement. Every summary sets `live_eligible` to false. There is no weighted survival score or automatic investment approval.

## Integration and remaining limits

[research/survival/pipeline.py](../apps/engine/research/survival/pipeline.py), `variants`, builds baseline and local one-sleeve lookback changes using development dates, records failed attempts, and preserves exact return dates. `trial_family` deduplicates candidate identities on matching dates; `multiple_testing` exposes usable/unusable trials and explicitly marks the recorded-family inference exploratory. `overfitting` computes DSR and CSCV independently, preserves individual unavailable reasons, and refuses selective candidate downsampling above the configured limit.

`integrity` checks raw alignment/prices and reruns selected historical prefixes to detect sampled future dependence. Passing those checks does not prove every strategy or data source causal. Selected universes still lack a point-in-time membership/delisting ledger. Exchange-calendar completeness and corporate-action correctness require separate verified inputs. Previously examined archived history remains exposed history, regardless of split names. Synthetic fixtures validate mechanics only.

`regimes` accepts optional HMM labels only with `train_only_forward_filter` provenance and lags them before conditioning returns. The HMM class itself does not enforce train-only fitting; its caller contract and reset behavior are documented in the accounting audit. Conditional regime samples are noncontiguous and do not become independent observations.

## Regression evidence and resume checklist

[tests/test_survival_statistics_audit.py](../apps/engine/tests/test_survival_statistics_audit.py) contains independent numerical checks:

- A hand-constructed six-partition CSCV example has PBO 0.75 under every candidate permutation, equal partition mass, and disclosed tail exclusion.
- HAC matches an explicit Bartlett covariance sum at lags 0, 1 and 5; DSR matches direct moments and `NormalDist`; BY matches a hand-computed harmonic adjustment.
- Fixed bootstrap block starts verify wrapping, truncation, compounding and drawdown against explicit paths.
- Gate cases cover missing values, NaN/infinities, booleans, strings, JSON-safe evidence, absent required layers, unevaluated failure gates, mandatory integrity and hard-failure precedence.

These are descriptions of saved test source, not a claim that this documentation task ran tests. Record actual commands and results in the audit run ledger. On resume, run the focused statistical tests and the full required Python/web/gateway checks, verify API/UI serialization of weighted CSCV diagnostics, and preserve existing result snapshots. Unresolved statistical prerequisites should remain visible as unavailable; changing thresholds is not a repair for missing evidence.

## Executed verification
The original focused statistical/accounting/provenance batch passed 54 cases. The accounting follow-up added five cases; the complete configured Python suite now passes 309 cases. See [verification](verification.md) for commands, scope, the deterministic clock fixture and warnings.
