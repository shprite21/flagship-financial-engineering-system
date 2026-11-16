# Q V2 — audit, changes and readiness

Finalized 5 October 2026; numerical validation ran 4 October. Development is confined to `C:\quant\terminal-v2`. The user's explicit version 1 path, `C:\quant\terminal`, supersedes the older location in the pasted brief.

Subsequent extension, 5 October: the [single-strategy lifecycle](single-strategy-lifecycle.md) builds on this audit and reuses its engines and integrity boundaries. It adds versioned projects, reserved OOS access, frozen candidates, forward links, comparisons and reports. Final verification is now **430 passed cases** plus TypeScript/build, browser acceptance and project-export replay; see [executed evidence](single-strategy-verification.md). Counts and verdicts below describe the original audit milestone.

## A. What the project is now

Q is strongest as a **reproducible systematic-equity research and strategy-survival platform**. Its real Python pipeline connects signals, constrained portfolios, net backtests, chronological evaluation and statistical diagnostics through a local gateway and React interface. It has strict-accounting and prospective-simulation modules, but no complete live execution system.

The main catalogue exposes eight strategies in three families. Its 18 Survival reporting layers combine calculations with explicit unavailable states. Immutable evidence, preserved negative outcomes and exact replay are a stronger application story than terminal breadth.

Read the [architecture/status map](audit-architecture.md), [accounting audit](audit-accounting.md), [statistics audit](audit-statistics.md) and [README diagram](../README.md). These trace active paths and retained libraries; tests prove specific invariants, not universal correctness.

| Hiring signal | Actual evidence | Limitation |
| --- | --- | --- |
| Statistics/inference | HAC, bootstrap, BY, conditional DSR, exact CSCV | Assumptions and search-family completeness remain |
| Time series/signals | Eight catalogue strategies; chronology/prefix perturbations | Fixed rules and selected universes |
| Portfolio/risk | Bounded weights, volatility/exposure controls, drift, attribution, drawdown, VaR/ES | Fractional accounting and estimator limits |
| Execution realism | Separate whole-share cash/volume stress and strict accounts | Modeled fills, not calibrated market impact |
| Research discipline | Frozen configurations, preserved failures/rejections, separate forward evidence | Retrospective history is not untouched OOS |
| Reproducibility | Hashes, replay, bounded workers, 397 passed test cases | Local services, not distributed execution infrastructure |

## B. Major problems found

- CSCV's first-column tie rule let candidate ordering change PBO; missing/nonfinite gate evidence could be handled incorrectly.
- Allocator renormalization and fallback paths could violate caps.
- The generic HMM used Viterbi/smoothed predictions; full-sample fitting remains a separate leakage risk.
- Sortino used the standard deviation of negative observations; undefined ratios appeared as zero. Some reports lost first-period drawdown or counted passive drift as turnover. Constant-weight backtests omitted the trading costs of restoring weights after price moves.
- Backtest lag/data/insolvency cases lacked guards.
- Snapshot reuse trusted mutable CSVs; invalid benchmarks could produce misleading returns.
- Old Node workers could reject replacement-worker jobs; serialization failures leaked admission slots.
- V2 could inherit V1 ports/stores/runtime. UI recovery instructions targeted the wrong API.
- A top-level optional ARIMA import could disable unrelated catalogue/frontier features.
- Synthetic Open could lie outside High/Low. Multiple retained engines also obscured account-model boundaries.

## C. Changes made

| Files/components | Change |
| --- | --- |
| `research/survival/statistics.py`, `models.py` | Uniform weighted CSCV ties; disclosed weights; complete finite gates; protocol 1.1.0 |
| `portfolio/allocation.py` | Final cap enforcement, residual cash and feasible checked fallbacks |
| `regime_detection/hmm.py` | Forward filtering; fit interval/overlap metadata; complete state mapping |
| `analytics/metrics.py`, `tearsheet.py` | Downside RMS, unavailable ratios, initial NAV and executed turnover |
| `backtesting/engine.py`, `data/models.py`, `data/features.py`, `analytics/factor_exposure.py` | Input/lag/insolvency guards, daily constant-weight restoration costs, preserved asset gaps and causal descriptive proxies |
| `apps/research_api.py`, `research/workspace.py` | Snapshot-byte verification, benchmark validation, unavailable-Sharpe gate blocking |
| `scripts/run_research.py`, `scripts/representative_experiment.py` | Valid demo bars; fixed full API experiment and replay |
| `qresearch/modeling.py` | Optional ARIMA failure isolation |
| `apps/gateway/quant-pool.mjs` | Per-worker ownership and cleanup |
| Launcher, gateway/Vite and test configuration | Separate 5273/5274 ports, listener ownership, pinned V2 stores/Python, isolated test paper stores |
| `research-workspace.tsx` | Visible workflow and correct disconnected setup instructions |
| New regression tests, `verify-v2.ps1`, README/docs | Independent checks, reproducible verification, research-first story and limitations |

The final follow-up added five constant-weight accounting cases, including independent dollar/share ledgers for daily/weekly updates and long-only/short holdings. Four reproduced the former undercharge before the fix. A paper-event test now uses a controlled clock and explicitly rejects a mark at the signal-receipt timestamp, removing dependence on Windows clock resolution without relaxing prospective rules.

Good components and compatibility imports were preserved. No broad rewrite, new speculative strategy, broker connection or deployment was added. Historical origin code remains where imports or old artifacts require it.

## Improvements ranked by resume value

### MUST FIX BEFORE RESUME

| Item | Outcome | What it proves to a recruiter |
| --- | --- | --- |
| Statistical tie/gate errors | Fixed and independently tested | Selection-bias and unavailable-evidence reasoning |
| Caps, accounting, metrics, lag/insolvency | Fixed in inspected paths; account distinctions documented | Numerical correctness and invariant testing |
| Snapshot/benchmark integrity and worker lifecycle | Fixed and tested | Trustworthy reproducibility/failure handling |
| Overclaims of true OOS/live returns | Excluded from narrative | Research honesty |
| V1/V2 isolation | Separate ports/runtime/stores and source hash comparison | Controlled development |

### HIGH-ROI IMPROVEMENTS

| Improvement | Status / next step | Capability proved |
| --- | --- | --- |
| Fixed experiment, rejection and replay | Implemented; 12 invariants passed | Complete reviewable research process |
| README, methodology, interview map | Implemented | Clear explanation of assumptions/trade-offs |
| One prespecified observed-data study | Future: freeze data/universe and retain every attempt without outcome-driven tuning | Market intuition and empirical research discipline |
| Genuine forward observation period | Future with explicit feed/calendar; keep zero observations until collected | Separation of retrospective and prospective evidence |
| Auxiliary data timing/gap review | Remaining before promoting macro/sector/HMM paths | Point-in-time information discipline |
| Fresh-environment install/CI | Remaining; locks/local checks exist | Portability beyond one machine |

### OPTIONAL / LOW ROI

| Addition | Why applications should not wait | Capability if pursued |
| --- | --- | --- |
| More strategies/indicators | Existing eight already exercise the research problem | Breadth; little value without a new hypothesis |
| Live brokerage/distributed execution | Much larger operational scope | Execution engineering |
| More exotic regimes/options models | Existing labs exceed the central story | Model comparison, only with valid data/tests |
| UI redesign/generic terminal features | Does not repair validity | Product/UI skill |
| Tests mirroring implementation | Prefer independent reference calculations | Test quality, not inflated counts |

## D. Remaining issues

No untouched historical holdout, proven alpha, point-in-time constituent/delisting database or universal calendar/action audit is established. Auxiliary feature fills/timing still require review. Fractional, constant-weight, strict daily and whole-share accounts are different. Constant-weight restoration costs are now included, but fractional sizing still uses pre-cost NAV with implicit cash/financing and lacks funded-account or settlement enforcement.

HMM filtering is causal conditional on trained parameters; callers must fit scaling/model/state order on training data. Generic `fit_predict` does not enforce that separation, and prediction calls reset the prior. DSR's effective-trial/IID assumptions are not identified by five correlated neighbors; CSCV/BY cover only recorded comparable attempts.

Costs, borrow and participation are modeled, not calibrated impact, short locate or complete funding/settlement. Paper machinery is implemented/tested, but the demo has zero forward observations and no broker verification. Production live execution, reconciliation/compliance and operational alerts remain absent.

The [browser end-to-end run](e2e-run.md) verified research submission, all 18 layers, result tabs, persistence, export and replay with no JavaScript errors; it did not cover every control. There is no authenticated external feed/broker, fresh-machine installation, global lint-clean or deployment claim. V2 is a local uncommitted Git repository; no remote was invented or publication performed.

## E. Resume-ready capabilities

Eight strategy implementations, constrained allocation, net accounting, chronological validation, statistical diagnostics, negative-result preservation, immutable Survival artifacts and exact replay are demonstrable.

The fixed experiment exercised 900 synthetic bars, ten main forward windows, five local candidates, 300 bootstrap samples, 70 CSCV partitions and three cost multipliers. These are coverage measurements, not investment performance.

**309 Python + 49 web + 39 gateway = 397 passed cases**, plus TypeScript/build success. The latest fixed experiment passed all 12 invariants and exact replay after the constant-weight correction. [Verification details](verification.md) disclose warnings, the repaired timing-dependent test and historical UI exclusions.

## F. Final three quant resume bullets

- Implemented HAC inference, block-bootstrap intervals, multiple-testing correction and CSCV/PBO diagnostics to assess return uncertainty and selection risk across recorded strategy trials.
- Built a reproducible equity-research workflow covering 8 strategies, constrained allocation and cost-aware walk-forward evaluation, with frozen data, configuration and source snapshots.
- Modeled whole-share cash and volume constraints with delayed execution and 1×–3× cost stress; preserved rejected experiments and kept forward paper evidence separate from backtests.

## G. Final three MFE application bullets

- Developed a Python research framework linking time-series signals, constrained portfolio allocation and chronological validation across 8 equity strategies, with explicit data and execution assumptions.
- Implemented HAC, block-bootstrap confidence intervals, multiple-testing correction and conditional DSR/CSCV diagnostics, supported by independent numerical tests for statistical and accounting invariants.
- Designed reproducible experiments using data/source fingerprints and immutable evidence; verified an end-to-end synthetic workflow while distinguishing research methodology from empirical market performance.

## H. Recommended title and description

**Q — Reproducible Strategy Research | Python, NumPy, pandas, statsmodels, SQLite**

An equity-research platform combining cost-aware portfolio backtests, statistical robustness diagnostics and reproducible experiment records, with prospective paper evidence kept separate from historical simulations.

## I. Interview preparation

The [15-question interview map](resume-and-interviews.md#what-i-must-be-able-to-explain-in-an-interview) links each topic to real functions: causal timing, walk-forward/OOS, HAC, bootstrap, BY/family completeness, DSR, CSCV ties, ratios/drawdown, cash/costs, constraints, HMM leakage, data biases, replay, paper and architecture.

## J. Readiness verdict

| Area | Classification |
| --- | --- |
| Core hypothesis → signal → portfolio/backtest → persisted evidence | **Ready to demonstrate** |
| Statistical implementation and independent formula checks | **Ready to demonstrate**, with prerequisites disclosed |
| Exact export replay and preserved negative results | **Ready to demonstrate** |
| Fractional accounting and separate whole-share stress | **Ready to demonstrate**, as modeled research |
| Selected-universe market-data research | **Implemented but needs improvement** |
| Generic HMM and auxiliary features | **Implemented but needs improvement** |
| Prospective paper service | **Implemented but needs improvement**; no demonstrated track record |
| Options/market-making/forecast/basket labs | **Experimental** |
| Production live trading, reconciliation/compliance and alerts | **Not implemented** as a complete system |
| Proven profitable strategy or untouched OOS track record | **Not implemented** / not demonstrated |

The core is ready for a bounded research-methodology demonstration and defensible resume wording. Empirical-performance and production-trading claims require new evidence.

