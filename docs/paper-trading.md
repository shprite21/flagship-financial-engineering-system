# Flagship systematic paper trading

Flagship now has a prospective paper-account service, distinct from historical backtests, the old browser account simulator, and user-recorded Survival evidence. All fills are labeled `q_simulated`; broker verification and live order submission remain false.

## Use in the terminal

1. Choose **Deploy saved result to paper** from Backtests, **Deploy saved portfolio to paper** from Portfolio engineering or Allocation replay, or deploy a saved custom project version.
2. Review the frozen draft: market, provider adapter, capital, schedule, costs, participation and risk limits. Defaults are configurable modeling assumptions, not exchange fee schedules. Choose daily bars first, or one-minute bars for intraday execution.
3. A standalone strategy gets independent capital. Combined allocation blends targets in one shared account. Funded sleeves receive separate cash budgets; selecting this mode for a saved research portfolio expands its saved sleeves. The setup can also add strategies from existing frozen paper drafts. Budgets must sum to one. Existing test accounts are never transferred into the new portfolio.
4. Save, check readiness, then activate. An unconfigured provider cannot activate. USD and INR accounts have separate totals, with no implicit FX conversions.
5. The gateway starts the Python runner when Flagship starts; it does not depend on an open browser. The computer and gateway must remain running. Start/stop runner controls affect scheduling; pause cancels pending orders for an account. Resume retains holdings and cash. Stop archives marked holdings without inventing liquidation trades. Simulated liquidation queues bounded market sells and continues on eligible decisions until holdings are sold, subject to liquidity and data availability.

The dashboard shows actual holdings separately from intended targets, cash reservations, unsettled proceeds, dividend receivables, orders, modeled fills, NAV, drawdown and processing exceptions. Copy the deployment ID into Survival's automated-record field to evaluate the exact saved research mandate. A funded or altered mandate cannot masquerade as that original research portfolio. Existing manual paper records are untouched.

## Provider connection contract

### Selected US integration: Massive data and Alpaca paper execution

The selected broker-paper architecture is Massive for strategy data and Alpaca's paper account for eventual order execution. Flagship's existing simulator remains a distinct execution source; activating a Flagship simulation does not send Alpaca orders.

**Implemented connection stage:** Connections and Deployments include an Alpaca paper connection and an on-demand account snapshot (USD balances, positions and latest 100 orders). Only `https://paper-api.alpaca.markets` is addressable. Authentication is verified against an active USD paper account; there is no configurable live URL and no order-submission endpoint. Account marks are reported by Alpaca, not relabeled as Massive prices. The snapshot is not a complete broker activity ledger, independent account allocation, or broker-verified real-money performance.

Enter paper keys in the local connection dialog or set `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_SECRET_KEY` in the gateway environment and select **Verify backend keys**. UI-entered keys remain only in gateway memory until disconnect/restart. They are not persisted in browser storage, logs, research context, or the Python engine's environment. Set `MASSIVE_API_KEY` in the backend environment or use the existing Massive connection dialog separately. Never put keys in source control or chat.

**Not implemented yet:** automated Alpaca order routing, durable broker order reconciliation, a prospective Massive feed publisher, and mapping independent deployments/funded sleeves to broker accounts. Broker deployment activation remains disabled. A connected paper account must not be presented as an operating systematic deployment. Alpaca paper fills will have their own execution model, distinct from Flagship's modeled fees, slippage and settlement. A single broker paper account also cannot be presented as multiple independent fresh-capital accounts.

References: [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading), [orders](https://docs.alpaca.markets/us/docs/working-with-orders), [Massive aggregates](https://massive.com/docs/rest/stocks/aggregates/custom-bars).

For Flagship simulation accounts, there is **no automatic conversion of Yahoo, Massive historical caches, CSV imports or synthetic scenarios into a forward feed**. To activate, a separately configured provider publisher must atomically replace `.data/paper-feeds/<provider>-<US|IN>-<1d|1m>.json`. The gateway exposes this only to the authenticated Python engine; provider credentials must remain in the publisher/backend. The selected Massive/Alpaca integration above does not yet publish this feed. Indian market provider selection remains separate.

`GET /integrations/engine/api/paper/catalog` returns the strict deployment, feed and order schemas. Each feed envelope includes:

- Explicit provider, source, market, interval and `raw` price basis; a UTC generated timestamp no more than five minutes old.
- Versioned calendar and market-rule identifiers. Sessions have explicit UTC opens, closes and settlement timestamps. Holidays are absent sessions, never synthesized weekdays. Coverage must include history and at least the next eligible session. Keep identifiers stable when extending the same calendar/rules; substantive changes require a new deployment.
- Completed OHLCV bars with symbol, session, start, end and original receipt timestamp. Daily bars cover the entire declared session; minute bars cover exactly 60 seconds. Duplicate, incomplete, future-dated and out-of-session bars are rejected.
- Split/dividend events with stable IDs and effective times, dividend payment times when known, and an explicit corporate-action completeness horizon. Unknown dividend pay dates leave cash in receivables. Split events precede dividends effective at the same instant; dividend amounts must therefore be in post-split units.

The publisher is responsible for verifying vendor entitlement, exchange-session coverage, raw price units, event completeness and the source of settlement dates. A file declaration is not independent vendor verification. Flagship checks schema, identity, timestamps and continuity but does not certify the external publisher. Missing feeds, stale heartbeats, revised previously consumed bars, calendar/rule changes and incomplete actions block processing visibly. The user must choose/configure actual providers before any market account can run.

## Decision and accounting conventions

- Decisions use only completed bars received by the recorded decision time. Daily decisions have a 60-minute arrival window after the close; minute decisions have a two-minute window. Older missed decisions are recorded as missed, never manufactured as timely signals. Activation starts with fresh cash; historical bars warm up rules but do not create past positions.
- Saved terminal and research adapters retain their daily-bar semantics. One-minute strategies use the explicit custom adapter; switching a saved daily strategy to minute lookbacks is rejected rather than silently changing its meaning.
- A modeled fill requires an eligible bar starting strictly after the recorded decision and no earlier than the end of the signal data. Daily market orders use the next eligible open. A receipt delay can make an opening ineligible; the service does not backdate decisions to obtain it.
- On restart, existing pending instructions may reconcile against subsequently received completed bars. Fresh decisions for elapsed windows are skipped. Partial/missing session groups stop progression rather than silently filling gaps.
- Market and stop fills include configured slippage; limit fills never violate the limit. Stop gaps use the worse of the opening and trigger prices. A stop-limit cannot fill within its activation bar. OHLC bars do not reveal queue position or intrabar ordering; those are not claimed.
- Liquidity capacity uses only volume received before the execution bar, multiplied by the configured participation fraction. All orders and funded sleeves share a per-instrument capacity budget; sleeve registration order gives deterministic priority when demand exceeds capacity. DAY orders expire at their eligible session close; GTC explicit orders persist until filled, cancelled, paused or superseded by a target rebalance. This is a participation cap, not a market-impact model.
- Buys reserve settled cash. Sells reserve held shares and credit unsettled proceeds until the supplied settlement time. Opening gaps recheck cash and exposure; buys clip to affordable whole shares. Sale proceeds do not fund same-session buys. Target sizing also respects existing gross exposure, so reallocation can take multiple sessions while sales settle.
- Splits adjust holdings and basis; fractional residuals become modeled cash in lieu at the next supported opening. Working instructions for the affected symbol are cancelled rather than retained in obsolete units. Dividends accrue to prior holders, with payment into settled cash only when a supplied pay time is reached.
- NAV reconciles to settled cash + unsettled proceeds + dividend receivables + marked shares. Prices use synchronized opening marks across instruments for fills and closing marks for final NAV. Drawdown halts and strategy failures pause the account and preserve previously valid accounting.

## Custom Python and JavaScript strategies

Saved source is resolved from Flagship's immutable development snapshot, not editor text. Add `paper_adapter.py` exporting `decide(context)` or `paper_adapter.mjs` exporting `decide(context)` to the strategy before saving its version. Select language and target/order output in deployment setup.

The context contains `schema_version`, decision/data timestamps, causal raw history, known corporate actions, the paper account, frozen parameters and persisted strategy state. Return exactly one of `targets` (symbol-to-weight map) or `orders` (an array satisfying the order schema), plus optional JSON `state`. Explicit orders support market, limit, stop and stop-limit with DAY/GTC. Limits/stops require minute data. Combined portfolios require targets; explicit-order strategies belong in standalone or funded accounts. Flagship, not the strategy, owns fills and cash.

Custom activation requires Docker with a Linux-container runtime and an already installed pinned image ID configured in `Q_PAPER_PYTHON_IMAGE` or `Q_PAPER_JAVASCRIPT_IMAGE` (`sha256:<64 hex characters>`). No image is pulled or installed automatically. The image ID is frozen with the deployment; configure it before registering the runnable version.

Workers receive no host mounts, forwarded credentials or network access. They run as an unprivileged user with a read-only root filesystem, dropped capabilities, no-new-privileges, a bounded temporary filesystem, CPU/memory/process limits, a 20-second deadline and bounded output. The source bundle is restricted to 2 MB and safe relative paths. The runtime/image checks fail closed. Host verification of actual Docker execution is still required wherever this optional runner is configured; an unavailable Docker runtime leaves custom deployments blocked, while trusted built-in adapters remain usable.

## Persistence, evidence and APIs

The private `.data/paper` store contains a SQLite checkpoint and an append-only hash-linked event ledger, plus immutable input/source snapshots. Registration freezes configuration, actual installed dependency versions and engine source. Changed engine code blocks execution and requires a reviewed new deployment; it never silently updates an existing account. No original research artifact is rewritten.

Events contain compact state changes rather than repeated whole-history snapshots. Checkpoints and event writes commit in the same transaction. Bar keys prevent duplicate fills on retry/restart. Export verifies the hash chain, frozen configuration, source/input snapshots and reconstructed checkpoint. This is deterministic ledger replay, not proof that a price provider's declarations are true.

The authenticated `/integrations/engine/api/paper` API exposes:

- `GET /catalog`, `GET/POST /deployments`, `GET /deployments/{id}`.
- `GET /deployments/{id}/readiness`, `POST /deployments/{id}/control` with activate/pause/resume/stop/liquidate.
- `GET /deployments/{id}/orders`, `POST /deployments/{id}/cancel-order`, and paged `GET /deployments/{id}/events`.
- `GET /deployments/{id}/export` and `/evidence`; automated evidence is labeled `q_automated_simulation` and stays separate from manually recorded paper events.
- `POST /runner/start` and `/runner/stop`. A fresh Flagship process starts its runner; per-account lifecycle state persists.

Survival accepts an optional `automated_record_id`, mutually exclusive with `forward_record_id`. Modeled costs are not represented as independently observed cost drift. Annualized performance inference remains suppressed in automated evidence until cadence and sample assumptions are independently reviewed. Minimum-observation rules still apply.

## Validation and operational limits

Paper tests cover independent cash/NAV invariants, fees, gap sizing, settlement, splits/dividends, partial fills, stop/limit behavior, missing sessions, revision detection, pause/resume, immutable exports, custom-source validation, API authorization and restart deduplication. Gateway tests check explicit feed selection and prohibit historical fallback. Run the required web quant tests, TypeScript checks, production build, gateway suite and Python suites before release.

This implementation does not include a configured vendor publisher, an installed custom-worker image, broker paper order routing, live orders, FX conversion, shorting, leverage, options, auction modeling or tick-level execution. The Alpaca connection stage above adds paper account inspection only. Provider-backed end-to-end acceptance and container isolation acceptance require the chosen external services/runtime; deterministic fixtures are not live-market verification.

### Verification record

- Complete Python suite: **248 passed**, including 22 focused paper tests. Existing Starlette deprecation and nonfinite skew-fixture warnings remain.
- Gateway suite: **27 passed**. Web quant and related research/portfolio/color contracts: **43 passed**.
- TypeScript checking, production application build and tracked-diff whitespace check: passed; Sites integration retained.
- Browser visual inspection could not run because the computer-use sandbox failed to start. No visual QA claim is made.
- No provider publisher or Docker executable was available/configured for actual market-feed or container execution acceptance. Readiness gates and deterministic fixtures were tested; external integration remains to be verified after configuration.
