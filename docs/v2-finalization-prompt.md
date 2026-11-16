# Q V2 — finalized implementation brief

## Product and finite scope

Q is a local systematic-equities research application in `C:\quant\terminal-v2`. Terminal V2 is the checkout/release, not another product. Finish the existing hypothesis → sealed data → signal/portfolio specification → development backtest → validation/stress → experiment comparison → frozen candidate → prospective protocol → monitoring → export/replay workflow. Reuse the existing services. Preserve V1 and all historical artifacts.

Institutional **research discipline** is the target; production execution readiness, profitable alpha and independently untouched historical data are not deliverables that software alone can establish.

## Audit before implementation

Read `implementation.md`, `audit-architecture.md`, `v2-methodology.md`, `strategy-survival.md`, `single-strategy-lifecycle.md` and `paper-trading.md`. Trace the active UI, gateway, queue, engines and stores. Verify older audit claims against current code and executable tests. Inventory retained paths without rewriting historical sources. Distinguish inspected code, passing tests, actual browser acceptance and unverified external services.

The existing map and methodology remain authoritative references. Record new findings, the lifecycle gap matrix, ranked backlog, target architecture, acceptance results and limits in `v2-finalization.md`. Do not repeat already completed features as proposed work.

## Implementation batches

1. **Integrity:** preserve the first reserved boundary for a captured dataset. Recapture/partition changes must never silently make sealed observations development data. Reject incompatible local partitions, retain failed attempts and protect old records. Test this before and after explicit OOS access, including existing conflicting records.
2. **Experiment review:** integrate a 2–4 trial comparison into Research projects. Use immutable project evidence, preserve failed/rejected attempts, show exact inputs, costs, evaluation dates, source identity, historical/walk-forward performance and validation status. Only overlay curves with verified matching data, evaluation dates and accounting conventions. Never forward-fill, silently truncate/rebase unequal windows, choose a winner, infer significance or calculate a new backtest in the UI.
3. **Product clarity:** make Research projects the default entry while retaining compatible deep links and auxiliary labs. Provide an obvious next-step path, explain pending/failed/empty evidence, and prevent stale asynchronous responses from changing the selected investigation.
4. **Verification and handoff:** extend the existing deterministic/browser examples to exercise comparison, retained rejection, OOS, freeze, empty forward registration, monitoring, reload, export and replay. Run all Python/web/gateway tests, explicit web quant tests, TypeScript and production build. Check changed UI lint; disclose remaining repository-wide lint debt. Update the README, architecture/methodology, demo and interview material with measured evidence.

For each batch: inspect before editing; reuse before creating; modify before duplicating; test before declaring complete. Define contracts and regression cases first. Keep UI, computation, data, storage and account execution separate. Review the changes against pre-edit snapshots; this checkout currently has no tracked baseline.

## V2 completion criteria

- One canonical example traverses the research lifecycle through a correctly empty prospective record and reproduces its archived results.
- Immutable lineage retains every attempted trial, negative outcome, decision, reveal and candidate freeze.
- Recapture of identical dataset bytes cannot bypass or relabel the reserved segment within an investigation; overlapping but different snapshots retain explicit prior-exposure limitations.
- Side-by-side review exposes comparability and research assumptions; incompatible curves are withheld with specific reasons.
- Existing numerical timing, costs, cash, sizing, statistical prerequisite and allocation invariants still pass.
- The browser exposes errors and unavailability, preserves the selected investigation and renders coherent evidence with no page errors in the canonical workflow.
- All required local test/type/build checks pass and their actual results are recorded.
- Documentation states implemented capabilities and external prerequisites without implying genuine forward performance or production readiness.

V2 completion does not require a favorable strategy result, authenticated market/broker accounts, elapsed future observations or publishing the local backend. Do not enable live orders or publish private research state.

## Deliberately deferred

V2.1+: point-in-time constituents/delistings, audited auxiliary release timestamps, signal IC/decay research, broader independent parameter/universe studies and fresh-machine CI execution. P3: authenticated feed publishing, broker reconciliation, compliance/settlement/approval operations and production execution. Existing advanced labs stay secondary until their own assumptions and data are defensible.

## Non-negotiable contracts

Use only past bars and lagged execution. Keep fractional research and funded whole-share accounts explicitly distinct. Preserve source/data fingerprints and refuse replay under different code. Label synthetic data and retain zero forward observations until actual evidence arrives. Gates are research policies, not investment approval; missing evidence is unavailable. Keep secrets backend-only, live submission disabled, UTC timestamps and explicit production session calendars. Preserve Sites hosting files/plugin. Positive returns/P&L are green, negatives red, zero/unavailable neutral; comparison curves have distinct fixed colors and matching legends.
