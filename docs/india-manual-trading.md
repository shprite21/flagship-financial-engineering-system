# India manual trading workflow

This extension is part of Q Terminal v2. Open **India manual trading** in the sidebar.
It never sends, modifies or cancels a broker order. All current evidence yields **NO TRADE**.

## Architecture

`apps/engine/india` owns observed ingestion, causal features, the current Groww cost model,
purged model comparison, CPU inference, manual ticket checks and an append-only actual-fill journal.
`india/api.py` is mounted under `/api/research/india`, behind Q's existing private gateway token.
Downloads and training use the existing bounded research queue. GPU training is a fixed module
subprocess using `Q_GPU_PYTHON`; credentials are stripped from its environment. The web view uses
the existing `/integrations/engine` transport, shared navigation and panel styles.
Q's existing fractional allocation backtester cannot represent this small whole-share, single-position
intraday account; this module explicitly uses a separate INR cash replay. Actual fills are separate
from both retrospective replay and Q's automated paper-account service.

Stores are under `.data/india/datasets/<sha256>`, `.data/india/runs/<UTC run ID>` and
`.data/india/manual-journal.sqlite`. Existing research artifacts and paper accounts are untouched.
The SQLite journal has update/delete prevention triggers, idempotent fill references and
transactional ticket reservation. A restart preserves reservations and actual fills.

## Run

From the checkout root, `./start-india-manual.ps1` launches the existing Q app and sets the GPU
interpreter to the user's existing `gpu-training/.venv` when present. Use another pair of ports
only if an existing Q session occupies the defaults. Do not store credentials in source or browser storage.

From `apps/engine` using the GPU environment's Python:

```powershell
python -m india doctor --device cuda
python -m india ingest --provider yahoo --start 2021-01-01 --end 2026-10-17
python -m india research --dataset <printed-sha256> --device cuda
python -m india verify --run <printed-run-id>
```

`--device cpu` is an explicit diagnostic alternative, never mislabeled GPU training.
Training needs NumPy, pandas and CUDA-enabled PyTorch. Terminal v2 inference needs only its
existing NumPy/pandas environment. Numeric JSON checkpoints avoid pickle and contain training-only
scalers, features, weights, temperature, seeds and dataset/source identities. `source.zip` archives the
module, and `checksums.json` protects the run artifacts. Reproduce under the recorded package and
hardware versions; numerical identity across different hardware/framework versions is not promised.

For read-only Groww ingestion, set `GROWW_ACCESS_TOKEN` in the local server environment and select
`--provider groww`. The adapter allowlists only GET historical candles and quotes. No order routes,
SDK trading client or credentials UI exist. Its authenticated contract is unit-tested but has not
been exercised against this user's account. No subscription was purchased. Groww currently lists
₹499 plus GST monthly; the research report shows this overhead separately from execution costs.

## Research specification

Fixed universe: RELIANCE, ICICIBANK, SBIN, ITC, INFY, HINDUNILVR, AXISBANK, LT.
It is a selected contemporary survivor sample, not historical point-in-time index membership.
Raw downloaded responses and excluded invalid rows are retained. No observations are fabricated,
forward-filled or silently replaced. Yahoo split-adjusted OHLC are converted to reconstructed
nominal units using returned split events. This is **not certified raw exchange history**;
demergers, omissions, revisions and nominal-price reconstruction remain audit requirements.

Features use only the signal-session close and older observations: 1/5/20-session returns,
20-session volatility, five-session range, turnover ratio, 50-session trend and opening gap.
The next observed session's open/low/close define a stop-first intraday research proxy.
Incomplete-symbol sessions and labels jumping over missing source bars are excluded.
Daily data cannot prove the actual ordering of intraday execution, manual latency or a 15:15 exit.

Compare the fixed positive 20-session momentum/50-session trend rule against a regularized linear
classifier and a 16-unit tanh network with dropout. Two fixed seeds are averaged for each ML
candidate; no search over architectures or thresholds. A sequence model/regime classifier is not
justified by the sample size, costs and absent executable data.

Expanding train starts with 504 sessions, followed by 126 validation sessions and non-overlapping
63-session tests. Each boundary is purged by label end, with a five-session embargo. All symbols
share date partitions. Earlier validation selects the epoch; later validation chooses temperature.
Features/scalers never fit on test data. The last 126 sessions are reserved for the candidate selected
from development tests only. If none qualifies, no replacement is chosen using the final segment.
This is retrospective pseudo-OOS, not certified previously unseen or prospective evidence.

Selection requires at least 30 trades, positive net execution and API-overhead scenario results,
positive doubled-slippage performance, at least three and 60% positive folds, and ML Brier improvement
over fold-training prevalence. Rank qualifying candidates by net INR minus half max INR drawdown.
The thresholds are research filters, not a significance or investment approval claim. All failures
and checkpoints remain available. Gross costs, calibration, seed diagnostics and stress results are
reported; no unsupported Sharpe significance, DSR or profitability claim is made.

## Costs, risk and operational limits

Costs are the current resident-retail NSE equity schedule applied uniformly to historical proxy
trades. Brokerage includes its turnover cap; STT is conservatively rounded upward, and stamp duty,
exchange, SEBI, IPFT and GST are itemized. Delivery scenarios include DP fees. Reconcile actual
contract notes because rounding/aggregation, gender and multiple orders can change totals.
Slippage assumes 10 bps per side (5 spread, 2 impact, 3 manual latency), stressed at 20 bps.
These components are assumptions, not measured fills. The daily replay conservatively withholds sale proceeds until after one further complete observed session; recorded actual fills require explicit settled-cash reconciliation. Late broker square-off adds ₹59 including
GST per incident; auction, circuit and overnight-gap losses have no modeled upper bound.
API/data subscriptions and income taxes are not per-order fees. API overhead is shown explicitly;
personal income tax cannot be estimated without the user's tax circumstances.

Only long whole-share NSE cash positions are supported. No shorting, leverage, MTF or automatic
order execution. Cash includes entry fees; the ₹50 planned stop loss includes both legs' fees and
exit slippage. Weekly losses use gross losing realized P&L without offsetting gains, plus reserved
open risk, against ₹150. Gaps may exceed these limits and must be journaled rather than rejected.
Cash is capped at ₹5,000; sale proceeds require an explicit settled-cash reconciliation before reuse.

Tickets require verified calendar, prior-session features, a server-owned eligible research artifact,
current quote/depth, spread and circuit checks, actual opening-cash reconciliation, no open ticket
and sufficient risk. Tickets expire after ten seconds. Manual entry window is 09:15–09:20 IST;
the intended exit deadline is 15:15 IST. Those times require intraday validation before promotion.
Groww's returned last-trade timestamp is not proof of a fresh order-book timestamp; that remains
a live-data blocker. Unknown calendar years fail closed. The 2026 holiday schedule is verified;
special sessions require separate explicit support.

No current dataset is marked execution grade, and no report automatically enables live tickets.
There is deliberately no UI override for rejected evidence. A future promotion requires independently
audited raw intraday data/actions/session metadata, timestamped executable depth, measured manual
fills, contractual costs, instrument restrictions and prospective validation, with reviewed code and tests.
The present release is a research/manual-workflow foundation, **not deployment-ready for capital**.

Options remain disabled: no current verified contract master, lot size, executable premium/spread
or evidence exists. Any future long-option ticket must fit **full premium loss plus fees** within ₹50,
as well as ₹5,000 available cash; a stop alone cannot establish maximum option risk.

## Sources checked 2026-10-17

- [NSE trading calendar](https://www.nseindia.com/resources/exchange-communication-holidays): October 20 closed for Dussehra; October 19, 21, 22 and 23 scheduled normal sessions.
- [Groww pricing](https://groww.in/pricing), [brokerage cap](https://groww.in/help/stocks%2C-f%26o-%26-ipo/searchable/how-much-is-the-brokerage), [delivery charges](https://groww.in/help/stocks%2C-f%26o-%26-ipo/sx-pricing/what-is-the-charge-for-buy-order-delivery).
- [Groww API pricing](https://groww.in/trade-api), [historical endpoint](https://groww.in/trade-api/docs/curl/backtesting), [quote endpoint](https://groww.in/trade-api/docs/curl/live-data).
- [PyTorch Blackwell support](https://pytorch.org/blog/pytorch-2-7/). Local executable forward/backward and CPU parity checks are the compatibility evidence for this machine.
