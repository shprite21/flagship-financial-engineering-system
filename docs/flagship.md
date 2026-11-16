# Flagship operation and workflow map

Flagship is the active research system. Legacy names identify the origin of integrated code and records, not separate products.

## Start and stop

Install locked dependencies as described in the [README](../README.md), then run `./start-flagship.ps1` and open `http://127.0.0.1:5273`. Node.js 24+ and Python 3.12+ are required. A fresh clone does not include installed dependencies or historical research records.

The gateway starts Python on demand through an authenticated loopback connection. One bounded executor handles shared Python research work, while the terminal daily backtester has a separate Node worker. Queue-full responses require retrying when work finishes.

Stop through the launcher. The Python service watches the gateway's owner pipe and exits when it closes. Interrupted work is marked failed/interrupted on restart; completed snapshots remain readable. These are local research jobs.

## Workflow map

| Workspace | Scope |
| --- | --- |
| Markets / Data | Exchange catalogues, explicit provider selection, historical CSV imports, source labels and immutable datasets. |
| Strategies / Backtests | Five long-only templates, historical daily backtests, indicators, parameter editing and result comparison. The scanner uses loaded datasets. |
| Portfolio engineering | Mandates, supported strategy sleeves, regime/allocation/risk settings, validation windows, experiment comparisons and PM decision history. |
| Allocation replay | Weighted historical portfolios, benchmark comparison, attribution, saved portfolios and JSON/CSV transfer. |
| Strategy Survival | Eighteen evidence layers with explicit failure/warning states, preserved trial history, and separate prospective paper records. |
| Trading lab | Daily/intraday provider or synthetic studies, independent A/B periods, warm-up, cash, costs, modeled participation and report exports. |
| Market making | Synthetic queue, inventory, fill and latency scenarios; modeled atomic hedges and scenario limitations remain explicit. |
| Advanced research | Versioned hypotheses, strict daily research and integrated options, cointegration, regimes and risk studies. |
| Artifact library | Local immutable research artifacts and any explicitly migrated historical records. Empty clones contain no private archive. |
| Deployments | Frozen strategy/portfolio paper accounts, local background runner, raw-feed readiness, whole-share daily/minute simulation and immutable exports. See [paper trading](paper-trading.md). |
| Connections | Provider authentication, Codex conversations and user-authenticated read-only broker access. |

Python-only strategy libraries remain Python APIs where the terminal does not expose a corresponding workflow. The retained full-library synthetic scenario selects pairs on the full sample. Portfolio Research keeps pairs unavailable pending train-only selection and calibration.

## Accounting conventions

Portfolio Research accepts 1–30 instruments. Own-price alpha sleeves support a single instrument; cross-sectional momentum requires at least two. The per-asset cap remains active, so a single-instrument study may retain substantial cash.

The Alpha sleeves view compares standalone net returns and provides sleeve NAV/drawdown, ending holdings, per-instrument gross return contributions, held-weight history, and a filterable/exportable simulated rebalance ledger. New evidence JSON snapshots retain all detail; older snapshots stay readable without being recalculated. Each standalone sleeve uses the same initial capital and evaluation window. Budgets weight the signal blend, not funded subaccounts: standalone sleeves do not sum to the constrained portfolio.

The comparison also plots the actual constrained total portfolio as a thicker solid line, with ending NAV and net return. Curves align by date, retaining gaps for missing observations. Multiple curves use distinct fixed colors with matching legends; line patterns provide an additional distinction. Only single-curve performance charts use green above the gain/loss baseline and red below it. For NAV, this baseline is initial capital, including when viewing a shorter chart range. P&L and return numbers remain green for gains and red for losses; zero and unavailable values are neutral.

Sleeve and portfolio skewness use the adjusted Fisher–Pearson sample coefficient of daily net returns over the warmup-excluded evaluation period; portfolio OOS skewness uses the saved walk-forward returns. Skewness is not annualized: negative indicates downside asymmetry, positive upside asymmetry. New results store null for fewer than three observations, constant returns or nonfinite inputs. Historical saved metrics are displayed as recorded; missing metrics stay unavailable and snapshots are not rewritten.

Sleeve diagnostics preserve the existing fractional-weight engine. Trade deltas compare the next session's executed weights to prior end-of-day drifted holdings; they are not share fills. Notionals and holding values are rebased to the evaluation starting NAV, retaining warmup positions. Instrument contributions are linked through NAV; their sum plus commission, slippage and borrow contributions reconciles to net return. Latest targets remain distinct from executed holdings. Cash/financing equals one minus net held weight; daily borrow enters performance but not the trading-cost column.

Terminal daily research uses raw execution prices, next-open whole shares, cash, costs, splits and dividend receivables. Portfolio research uses lagged fractional weights. Allocation replay uses provider-adjusted prices. Strict daily studies use explicit sessions and effective-dated accounting inputs. Bar labs use next observed opens; market making uses synthetic events.

Do not combine these into one performance series without reconciling timing, price basis, currencies, dividends, costs and sizing. See [data conventions](real-market-data.md).

## Local records and migration

`.data/market` and `.data/flagship` are private stores excluded from source control. Preserve them before environment changes. Source provenance is recorded in [the integration manifest](flagship-source-manifest.json) and the advanced engine's source manifest. Original projects and historical snapshots must remain available for verification.

Browser portfolios are origin-specific. Use the original application's export workflow and Flagship's Allocation replay transfer interface to import reviewed JSON. A new browser origin cannot read an old origin's storage directly. Existing workspace keys remain compatible; do not overwrite old records with newly calculated results.

Historical artifact replay may require the original code and dependency fingerprint. Machine-specific performance measurements and acceptance notes are local records, not public guarantees.

## Validation and limits

Run the source suites described in the [README](../README.md). `node apps/gateway/tests/flagship-runtime.mjs` is an additional migration-aware acceptance harness: it expects historical local records and is not a fresh-clone smoke test. Its generated output belongs under ignored local storage.

Broker authentication requires the account holder. Live orders, manual terminal paper fills and live-feed claims remain disabled. Strategy Survival monitoring is a read-only contract; passing research gates is not execution approval.
