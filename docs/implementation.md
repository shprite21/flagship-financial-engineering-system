# Flagship Financial Engineering System architecture

Flagship Financial Engineering System is the single active system. Open Research evidence for the four module workbenches and the retained study results. Historical `q21`, `flagship` and `evidence` identifiers preserve compatibility with stored data, imports and scripts. The earlier standalone projects remain references; new capabilities belong here.

## Service boundaries

| Component | Responsibility |
| --- | --- |
| `apps/web` | React/TypeScript interface, research views, browser workspace state and typed transport. |
| `apps/web/lib/quant.ts` | Daily indicators and historical share accounting, executed through the gateway worker for integrated backtests. |
| `apps/web/lib/paper.ts` | Separate local account-simulation rules; not a live execution service. |
| `apps/engine/paper` | Persistent prospective paper accounts, scheduling, frozen strategy adapters and daily/minute modeled execution. See [paper trading](paper-trading.md). |
| `apps/gateway` | Loopback integration service, provider access, dataset persistence, bounded Node computation and Python lifecycle. |
| `apps/engine` | Python research, portfolio allocation, validation, immutable artifacts and simulations. |
| `apps/engine/qmodules` | Company-report evidence, local semantic retrieval, optional AI/news adapters and the native synthetic economy; all use Flagship's existing research queue/store. |
| Broker adapters | User-authenticated read-only account access, separate from signal generation and backtesting. |

The web development proxy forwards `/integrations` to the gateway on `127.0.0.1:5274`. The gateway owns Python startup on an ephemeral loopback port with a private token, including its background paper runner. One bounded shared executor admits up to three queued/running Python calculations; a separate bounded Node worker handles terminal daily backtests. Overload is reported rather than silently admitting unlimited work.

## Research and data

Provider choice is explicit: Yahoo, Massive, imported CSV and seeded synthetic sources are available according to workflow. Provider-specific cache pointers and immutable dataset versions prevent silent substitution. Credentials remain in backend configuration or session memory.

Portfolio engineering hosts strategy research. Allocation replay is a separate dashboard in the Develop menu. Research runs preserve inputs, parameters, code identity and results; later edits create new studies. The Strategy Survival pipeline extends existing engines with independently visible integrity, robustness, statistical and forward-evidence layers. See [methodology and limits](strategy-survival.md).

Research projects adds a versioned single-strategy investigation over those services: thesis/literature, exact dataset, development trials, Survival, a reserved final segment, immutable strategy freeze, existing forward/paper records and a 21-section report. It uses the existing executor and immutable Survival registry. Research and prospective paper share the portfolio weighting adapter. See [lifecycle architecture, API, migration and limits](single-strategy-lifecycle.md).

Research projects is now the default workspace and first navigation item. Its comparison adapter reads the existing immutable project GET response; it does not introduce another API, calculation engine or store. Curve overlays require matching full/development data fingerprints, evaluation dates, engine source and account conventions, with an explicit initial NAV. Failed or incompatible trials retain descriptive columns. Project capture/trial/validation/reveal/freeze/forward guards reject conflicting partitions of identical dataset bytes while preserving old artifacts. See [finalization and verification](v2-finalization.md).

The terminal daily engine, portfolio-weight backtester, strict daily engine, bar lab and event simulations retain distinct accounting conventions. See [operations](flagship.md) and [data behavior](real-market-data.md). Generated synthetic observations are labeled and do not represent exchange sessions or live prices.

Company intelligence and Economy lab consolidate the remaining independent project capabilities. [Company intelligence](company-intelligence.md) freezes report bytes and page text, provides reproducible lexical search and model-identified local semantic indexes, and gates optional AI/news calls on explicit backend configuration. [Economy lab](economy-lab.md) runs the original native CPU model with per-step accounting checks and measured scaling studies. Neither module changes strategy accounting or execution permissions. The [consolidation audit](quant-consolidation.md) maps every source project to its Flagship destination.

## Strategy development

Custom strategy projects live in ignored `.data/codex-development/<project>/workspace` repositories. The gateway snapshots source before and after development turns and parameter changes. These projects are separate from fixed-template backtests; arbitrary development code is not loaded into the gateway or promoted to execution.

The local Codex integration uses scoped development permissions and strips credential environment variables. Native Windows read isolation has limitations; it is not a complete filesystem security boundary. Broker credentials must never enter browser state, logs or research context.

## Persistence and provenance

Local market snapshots and results live under `.data/market`; integrated research records use `.data/flagship`. These stores and any historical migrations are private local state and are absent from a fresh clone. Tests use explicit fixtures or isolated temporary stores.

The source manifests retain origin identifiers and hashes for migration verification. Historical source implementations are preserved where required by imports and reproducibility. Reproducing an old artifact may require its original code and dependency fingerprint.

## Execution boundary

Live orders and manual terminal paper fills remain disabled. Daily history is not an executable quote feed. Production risk, compliance, settlement, session controls, broker reconciliation and approval services must exist before live execution is considered. Research validation does not grant execution permission.

The separate systematic paper service accepts explicitly configured raw-data feeds with calendar, settlement and corporate-action metadata. It never promotes historical caches to live feeds. Provider selection and custom-worker configuration remain prerequisites; no provider or isolated worker is claimed connected by installing the code. The local gateway starts the runner independently of browser tabs.

## Build and validation

Use Node.js 24+ and Python 3.12+. Install web dependencies through `npm run install:ci` in `apps/web`, and Python dependencies through `setup-flagship.ps1` at the root. Keep both dependency locks, test fixtures, third-party license files, the Sites hosting manifest and Vite Sites plugin.

Run the web quant/contract tests, TypeScript checking, production build, Python tests and gateway tests as documented in the [README](../README.md). Quantitative changes require independent numerical invariants and edge cases, including future-data perturbations, costs, cash and corporate actions.
