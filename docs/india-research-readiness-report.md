# India strategy discovery and manual workflow — implementation report

As of **October 17, 2026, Asia/Kolkata**. Decision: **NO TRADE**. No candidate qualifies for
capital deployment, and no broker order was submitted. This is an implemented research and
manual-assistance workflow with measured GPU experiments, not a verified profitable strategy.

## Delivered

- Installed in **C:/quant/terminal-v2**: observed ingestion; causal feature pipeline; two GPU
  candidates and non-ML benchmark; purged chronological validation; CPU inference; versioned
  checkpoints; INR costs/cash/risk controls; manual tickets; actual-fill journal; authenticated
  routes; **India manual trading** dashboard and launcher.
- Added **06-india-manual-workflow** to the local clone of **shprite21/quant-research**, with a
  runnable entry point, protocol, retained measured results and this report. The canonical engine
  remains in Q rather than being duplicated in the portfolio repository.
- The user clarified that no separate quant-trading repository exists; Terminal v2 is the target.
- Terminal v2 has no initial Git commit and its existing files are untracked. No wholesale commit,
  reset or cleanup was performed. Original integration files were backed up before hash-checked
  replacement. Quant-research was cloned at `9fe70cc1c23ada39af5cda44632ec59dae7ee506`;
  changes are local and have not been pushed.
- The linked prior conversation was read, but its assistant responses resolved only to opaque
  content references. The current explicit user request and repository instructions define scope.

## Actual hardware and training evidence

| Check | Observed result |
|---|---|
| GPU | NVIDIA GeForce RTX 5070 Laptop GPU, approximately 8 GB VRAM |
| Driver | 617.42; driver-reported CUDA capability 13.4 |
| Python | 3.12.10 in the existing gpu-training environment |
| PyTorch / bundled CUDA runtime | 2.14.1+cu130 / 13.0 |
| Device architecture | Compute capability 12.0; installed wheel lists sm_120 |
| Real device computation | CUDA forward, backward and synchronization passed |
| Training | 36 GPU models: two architectures × two seeds × nine folds |
| Saved checkpoints | 45, including nine non-ML probability baselines |
| CPU parity | Maximum absolute logit error 3.66e-07 across saved training checks |
| Runtime separation | Terminal v2 inference works in its CPU environment without PyTorch |
| Integrity | 49 final run files verified against SHA-256 checksums |

`outputs/gpu-environment.json` records installed package versions. The Windows Store Python
launcher required execution outside the sandbox, but no packages or drivers were upgraded.
The final run archives numeric checkpoint JSON, protocol, dataset manifest and source ZIP.

## Data audit

Dataset: `ad9826a4c4056af1b0801bfecbb60f018d8f882f94387605b4617aa53cdbd335`. Observed Yahoo data: **11,433 retained rows**, eight equities,
2021-01-01 through **2026-10-15**. 23 invalid or
zero-volume source rows were explicitly quarantined with raw responses retained. No synthetic
fallback or forward-filled bars were used. Features start 2021-03-15. Historical symbols:
RELIANCE, ICICIBANK, SBIN, ITC, INFY, HINDUNILVR, AXISBANK, LT.

There is **no October 16 bar in this download**, so it cannot supply Monday October 19's required
prior-session features. The existing local cache inspected before ingestion was US/AVGO, and
the portfolio repository's included CSVs were simulation/example outputs rather than an audited
NSE execution dataset. No Groww token was available in the environment.

This is a contemporary selected-survivor universe, not point-in-time constituents or delisted coverage.
Yahoo prices are split adjusted; the code reconstructs nominal units using returned split events,
but those units, corporate actions, demergers and historical revisions are not exchange-certified.
Intraday data, historical bid/ask, depth, circuits and manual latency are unavailable. The Groww
GET-only historical/quote adapter is implemented; authenticated account integration is **unverified**.

## Measured comparison

Expanding training: 504 initial sessions; validation: 126 sessions; test: 63 sessions; five-session
embargo plus label-end purging. Date partitions are shared across symbols. Validation is split into
earlier epoch selection and later calibration. Two fixed seeds are averaged for each neural candidate.
Nine full test windows use signal dates **2023-09-28 through 2026-01-19**, totalling 567 sessions and
4,536 symbol observations. The remaining incomplete development window is not scored. The final
126-session segment begins **2026-04-15** and was **not evaluated for a selected model**, because
none passed. Its raw history is locally accessible; genuinely unseen status cannot be certified.

The execution proxy is next observed session open to stop/close, long only, integer shares, one
position, current Groww tariffs, 10 bps slippage per side, ₹5,000 starting cash, ₹50 planned all-in
loss per trade and ₹150 gross losing P&L per week. Sale proceeds remain unavailable until after
one further complete observed session. No borrowing or capital replenishment is assumed.

| Candidate | Trades | Net after trade costs ₹ | Fees ₹ | Max drawdown ₹ | Net at 2× slippage ₹ | Brier | Passed |
|---|---:|---:|---:|---:|---:|---:|---|
| momentum | 290 | -4,505.44 | 3,805.81 | 4,505.44 | -4,589.25 | 0.1266 | No |
| linear | 8 | -215.93 | 110.24 | 215.93 | -237.75 | 0.2257 | No |
| mlp | 0 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1257 | No |

The no-trade/no-subscription reference has zero trades, zero P&L and zero fees; interest is omitted.
The MLP's zero return is abstention, **not evidence of trading skill**. Its slight Brier improvement
over training prevalence (0.1267) does not establish economic edge.
The linear model is poorly calibrated and has too few trades. The benchmark's costs overwhelm
its already weak gross result. Individual fold and seed outcomes remain in `report.json`.

The API subscription scenario is a separate **economic** sensitivity, not an account NAV:
29 evaluated calendar months × ₹588.82 = **₹17,075.78** if a subscription is maintained throughout,
paid outside trading cash. After this scenario, momentum is
₹-21,581.22, linear ₹-17,291.71,
and the MLP ₹-17,075.78. No subscription was purchased.
If funded within ₹5,000, even the first monthly payment reduces deployable cash to ₹4,411.18.
The dashboard identifies trading-cost results separately from this fixed cost.

Three runs are retained: initial mechanics, fee/provenance audit, and this final settlement audit.
The two initial runs are superseded implementation evidence, not additional independent OOS studies.
Candidate architectures/thresholds were not tuned to rescue losses. Fee-cap, fixed-cost and
settlement corrections were made after inspecting initial output; this final study is therefore
explicitly **post-audit retrospective exploratory evidence**. No untouched confirmatory claim is made.

## Cost and execution readiness

The model itemizes brokerage, turnover cap, STT, stamp duty, exchange, SEBI, IPFT, GST and delivery DP
charges. STT rounding and a small rounding reserve are conservative. It applies current tariffs
uniformly to historical proxies, not historical fee schedules. Slippage is an assumption, not
empirically calibrated. Additional square-off cost is ₹59 including GST per incident. Auction,
overnight-gap and circuit losses are not bounded. Personal income tax, hardware and electricity
are not inferred. Actual all-in net performance remains **unverified**.

Manual tickets require valid session/time, prior-session features, eligibility, fresh quote/depth,
spread/circuit checks, whole shares, reconciled cash and atomic risk reservation. The opening cash
balance is unverified until the user reconciles it. The journal records actual partial fills and
fees idempotently, preserves adverse fills and halts new tickets on breaches. It never treats a
reconciliation as erasing a risk halt or automatically credits unsettled sale proceeds.

No execution-grade dataset or qualified model exists; the server refuses new live manual tickets.
There is no promotion override in the UI. Groww last-trade time is not a certified book timestamp;
instrument-master/tick/restriction verification and forward fill calibration remain required.
Long options are excluded because no current verified lot, premium/spread or full-premium-loss
capacity evidence exists. Future consideration must fit full premium plus fees within ₹50.

## Validation and application check

| Check | Result |
|---|---|
| Existing complete Python suite | 389 passed; 4 warnings; 154.53 seconds |
| Final India-specific tests after accounting correction | 17 passed; 1 dependency deprecation warning |
| Gateway suite | 39 passed |
| Web quantitative invariants | 16 passed |
| TypeScript | Passed |
| Production build | Passed |
| Browser | Loaded measured comparison; NO TRADE visible; signal check returned blockers; no tickets/fills manufactured |
| Checkpoint verification | 49 files passed under the CPU-only engine interpreter |

The full suite ran before the final settlement correction; the 17 targeted tests were rerun after
it. Those test sets overlap and must not be added as independent coverage. Existing warnings are
Starlette/httpx deprecation and pandas warnings from explicit undefined-skewness tests. Logs are
in the task's `outputs` folder and copied alongside this report where appropriate.

## Calendar and next operating state

NSE's verified 2026 cash calendar lists **Tuesday October 20 as Dussehra, closed**. October 19,
21, 22 and 23 are scheduled normal sessions, 09:15–15:30 IST. The module proposes manual entries
only at 09:15–09:20 and exits by 15:15, but the daily backtest cannot validate those fills.
Exceptional exchange circulars must still be checked before a session.

**Deployment status: blocked; capital allocation: ₹0.** Necessary remaining evidence is updated
raw intraday NSE data with complete actions/session metadata, historical executable spread/depth,
verified provider access and instrument restrictions, calibrated manual slippage, prospective
records, and a strategy that passes economic/risk gates. GPU training is available and tested;
a profitable implementable strategy has **not** been established.

## Local artifacts and launch

- Application: `C:/quant/terminal-v2`; sidebar **India manual trading**.
- Launcher: `C:/quant/terminal-v2/start-india-manual.ps1` (GPU Python set for the existing environment).
- Final installed run: `C:/quant/terminal-v2/.data/india/runs/20261016T203314983929Z`.
- Raw dataset: `C:/quant/terminal-v2/.data/india/datasets/ad9826a4c4056af1b0801bfecbb60f018d8f882f94387605b4617aa53cdbd335`.
- Research entry point: `C:/Users/arnaa/.codex/.chatgpt-projects/g-p-6a082dbdf6c88191af6a0817dd6ffc88/quant-research/06-india-manual-workflow/run_study.py`.
- Code review patch: `C:/Users/arnaa/.codex/.chatgpt-projects/g-p-6a082dbdf6c88191af6a0817dd6ffc88/outputs/terminal-v2-changes.patch`.
- Backups and installation hashes: task `outputs/terminal-v2-originals` and `outputs/installed-manifest.json`.

## Primary references checked October 17, 2026

- [NSE calendar](https://www.nseindia.com/resources/exchange-communication-holidays).
- [Groww pricing](https://groww.in/pricing), [brokerage cap](https://groww.in/help/stocks%2C-f%26o-%26-ipo/searchable/how-much-is-the-brokerage), [delivery charges](https://groww.in/help/stocks%2C-f%26o-%26-ipo/sx-pricing/what-is-the-charge-for-buy-order-delivery).
- [Groww API subscription](https://groww.in/trade-api), [historical API](https://groww.in/trade-api/docs/curl/backtesting), [quotes](https://groww.in/trade-api/docs/curl/live-data).
- [PyTorch Blackwell support](https://pytorch.org/blog/pytorch-2-7/); the actual local GPU checks are authoritative for this installed environment.
