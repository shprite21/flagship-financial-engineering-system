# Single-strategy lifecycle verification — 5 October 2026

This record supplements the [architecture/methodology/API guide](single-strategy-lifecycle.md) and original [V2 audit](v2-audit.md). V1 remains a read-only reference.

## Final checks

| Check | Executed outcome |
| --- | --- |
| Python | **342 passed**, 4 disclosed warnings; 72.06 seconds |
| Web quantitative/contract suite, including `tests/quant.test.mjs` | **49 passed** |
| Gateway unit/runtime integrations | **39 passed** |
| Total | **430 passed**, including 33 new lifecycle/allocation cases |
| TypeScript | Passed, `--noEmit --incremental false` |
| Production build | Passed; Sites plugin/hosting manifest preserved |
| Browser acceptance | All lifecycle stages passed; zero page errors |
| Browser-downloaded package | Two development trials, one reserved OOS and one Survival run replayed |
| Fixed example package | One development trial, one reserved OOS and one Survival run replayed |
| Original V1 baseline | All **347 files unchanged**, exact SHA-256 comparison |

Final log: `outputs/verification/lifecycle-full-final.log`. JUnit: `outputs/verification/python.xml`. Machine-readable [verification evidence](evidence/single-strategy-verification.json) records both projects, fingerprints and replay outcomes. Warnings are the existing Starlette/httpx deprecation and three pandas warnings in the deliberate nonfinite-input test. The pre-existing historical Streamlit UI exclusion remains; no new failures were skipped. Vinext's root-route classification warning did not prevent the build.

## Browser acceptance and saved project

The local app is available at [Q V2 Research projects](http://127.0.0.1:5273/?page=Research%20projects) while its launcher remains active. Open this saved project:

**SYNTHETIC lifecycle browser acceptance 2026-10-05T11:56:37.294Z**

Project: `f9c8ec7f93d6729a6ef30506d1095e7635f1b918049b19dc82b9501620c28c86`

StrategyVersionID: `1262a9e6f3e1870f5338c7aa4c2ede622b680c3b02c1a32791b915f28d156999`

The browser created a falsifiable momentum thesis, saved portfolio/protocol revisions, captured exact data, and launched prespecified 63- and 80-bar trials. Both outcomes remain. It rejected the diagnostic 80-bar neighbor because it was not the prespecified candidate, then validated the 63-bar candidate through all 18 layers. The robustness table displays all local configurations.

It revealed the reserved final segment once, verified a second reveal returned 409, froze the specification, registered an empty prospective protocol, viewed the separated comparison, downloaded Markdown and ZIP files, then reloaded and reopened the persisted project. It verified historical annualized metrics were present and all prospective metrics remained unavailable. Screenshots were inspected for labeling, layout and return colors.

Actions used the real Q UI/gateway/API, without mocked application responses. Data remained explicitly synthetic. Installed Edge was used through Playwright; no browser download or OS policy change was needed. The saved harness is `apps/web/scripts/project-e2e.cjs`: `Q_PLAYWRIGHT_MODULE` may point to an installed Playwright package, and `Q_E2E_BROWSER_CHANNEL` selects an installed browser (default `msedge`). Each run creates a separately labeled project.

Evidence: `outputs/verification/project-browser-final-20261005/`, containing `summary.json`, `replay.json`, `research-paper.md`, `research-project.zip`, and experiments/robustness/monitor/reopened screenshots. Earlier browser attempts remain separately labeled; accessible form names were fixed before final acceptance.

## Fixed example

The independent example at `outputs/project-example/20261005T115648725835Z/` uses fixed 63-bar momentum, signal weighting and eight synthetic instruments. The browser example separately selects equal weighting to exercise that adapter.

All eight assertions passed: single strategy, reserved data excluded from development, 18 layers, recorded reveal, immutable freeze, empty prospective record, 21 report sections, and live execution disabled. Replay subsequently verified stored weights, holdings, NAV, OOS and Survival outputs against recorded source/dependencies.

Both examples report **1 PASS, 14 WARN, 0 FAIL, 3 N-A**. Research gates satisfy their recorded default required-layer policy; the overall outcome remains **WARN**. DSR is unavailable without defensible effective-trial/IID assumptions. The browser example's reserved synthetic return is negative (approximately −4.01%); it was preserved. Synthetic prices establish no empirical profitability.

## Boundaries

No prospective observations or fills were invented; registration is not a track record. Automated paper-draft persistence and feed-readiness rejection use isolated contract fixtures; existing paper tests cover deterministic fills, cash, costs, settlement, restart and controls. No authenticated feed, broker performance or live execution was verified. Source changes intentionally invalidate replay/promotion against a different installed engine; older archives retain their original source.

Unsupported allocation adapters, broader robustness grids, signal drift/decay, calibrated implementation shortfall, prospective annualization and independent unseen-OOS certification remain in the [limitations table](single-strategy-lifecycle.md#remaining-limitations-and-supported-scope).
