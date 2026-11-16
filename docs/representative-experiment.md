# Representative research experiment

**SYNTHETIC MECHANICS DEMONSTRATION — NOT MARKET PERFORMANCE**

Executed 4 October 2026 through the research API, followed by Survival export and exact replay. The protocol was fixed before the run; no optimization selected a favorable result.

## Reproduce

From `apps/engine` after setup:

```powershell
.\.venv\Scripts\python.exe -m scripts.representative_experiment
```

A fresh directory is created under `outputs/research-demo`. An explicit `--output` must be empty; earlier outcomes are preserved. The script saves research files, SQLite Survival records, a ZIP export and summary. Re-running creates new IDs/timestamps; numerical reproducibility is checked from each frozen export.

The [portable summary](evidence/representative-summary.json) is checked in. Full local evidence is in `outputs/research-demo/20261004T143732655292Z`, including `survival-export.zip`. That ZIP was replayed successfully. Generated data/source archives remain ignored; the script regenerates a complete pack. Historical replay requires matching archived source and dependencies.

A [new summary](evidence/representative-summary-20261005.json) records the fixed protocol rerun after the constant-weight library correction on 5 October (Asia/Calcutta). Local evidence is in `outputs/research-demo/20261004T204803640711Z`. All 12 checks and exact replay passed, with the same 1 PASS / 15 WARN / 2 N-A outcome. The main demonstration uses drifting holdings, so this rerun verifies integration and provenance; the independent constant-weight tests verify the repaired accounting branch. Earlier artifacts remain intact.

## Prespecified protocol

| Item | Configuration / observed count |
| --- | --- |
| Data | 900 synthetic weekday observations, seed 7, eight assets; 2018-01-01 to 2021-06-11. Ticker labels do not make these market observations. |
| Signals | Time-series momentum, lookback 63, 60% sleeve budget; mean reversion, lookback 20, 40%. |
| Main account | 1,000,000 starting units, long-only, weekly decisions, 20% asset cap, 100% gross/net ceiling, 10% volatility target; fractional drifting portfolio. |
| Costs | 2 bps commission + 3 bps slippage per side; 1×, 2× and 3× cost multipliers. |
| Main evaluation | 126 warmup bars excluded; 774 evaluated returns; 10 complete 63-bar forward tests after a 252-bar initial training window. |
| Survival validation | 60/20/20 chronological segments; eight capped forward folds before the final segment, totaling 504 test observations. |
| Parameter diagnostics | Five recorded candidates: baseline plus one-sleeve lookback perturbations. No winner promoted. |
| Bootstrap | 300 circular block samples, block length 10, seed 42, 95% percentile intervals. |
| CSCV | Eight blocks, 70 half-block partitions, five candidates; three trailing development observations disclosed as excluded. |
| Execution | Separate whole-share next-close account; 1% participation based on prior volume, with delay/slippage stress. |
| Prospective evidence | Frozen registration; zero observations. No invented fills or backdated forward performance. |

## Outcome

All **12 script invariants passed**: API result/artifact identity, all 18 layers reported, no calculation errors, no hard integrity failure, attribution reconciliation, monotone cost stress, cache reuse, exact export replay, blocked synthetic promotion, preserved rejection, no invented forward observations and disabled live eligibility.

Survival reported **1 PASS, 15 WARN, 0 FAIL, 2 N-A**. Default research gates were satisfied because integrity is the default required layer. That does not clear the original mandate: synthetic data blocks paper-candidate eligibility, and the experiment was explicitly rejected for empirical investment use.

Weak or unavailable evidence was preserved:

- One-sided HAC mean-return p-value: **0.2899**.
- Minimum BY-adjusted p-value across five valid tests: **1.0**.
- Conditional local-grid PBO: **0.6571**.
- DSR: **unavailable** without an effective independent trial count and IID assumption.
- True untouched OOS, forward performance and live performance: **unavailable**.
- The bootstrap Sharpe interval includes negative and positive values.

The synthetic execution baseline recorded 817 fills, 12 clipped orders and minimum cash of about 1.62 units. These are fixture outcomes, not execution quality or market-capacity claims. Fractional and whole-share outcomes differ because sizing, cash, timing and participation differ.

## Issues exposed and interpretation limits

The synthetic generator previously allowed opening gaps outside High/Low; bars now enclose both Open and Close. Archive reuse did not verify saved CSV hashes; it now rejects tampering. Invalid benchmark values could become zero returns; the main workflow rejects an invalid benchmark before research. Independent regressions cover each repair.

The main and Survival walk-forward scopes differ and are reported separately above. API verification checks the representation consumed by the frontend. A separate [browser run](e2e-run.md) exercised research and Survival with default lookbacks, persistence and export; neither run establishes external-feed verification or prospective observation over time.

