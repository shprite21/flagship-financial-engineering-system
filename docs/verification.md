# Flagship release verification

November 16, 2026. The terminal started on its local launcher. A browser check opened each of the four research workbenches from Research evidence and checked the selected engine action. Changing HMM execution cost from 5 bp to 0 bp changed the on-screen Sharpe from −0.14 to +0.12 and CAGR from −0.85% to +0.47%. The default view was restored after the check.

| Check on the flagship checkout | Outcome |
| --- | --- |
| Historical study evidence | Independent standard-library verifier matched four ledgers, 1,255 OOS dates, five cost treatments, source hashes and chronological fold boundaries. |
| Derivatives and multi-asset risk study | Complete model rerun reproduced the committed JSON byte for byte. |
| Web tests | 67 passed, including the 16 daily-quant tests. |
| Local gateway integration tests | 39 passed. |
| TypeScript and production build | Passed. |
| Python engine suite | 385 passed. Windows Application Control blocked the newly compiled optional economy executables in four tests (WinError 4551). |
| Read-only paper receipt | Both validation and privacy tests passed. The audit found zero prospective observations. |

The four blocked tests cover the additional native agent-based economy. All tests for HMM, cointegration, derivatives, allocation, forecasting and multi-asset risk completed successfully. The supplemental dashboard's optional PDF exporter also encountered a Windows native-extension restriction. Its tested features and limits are recorded in the [labs guide](../research/labs/README.md). The retained [historical ledgers](../research/validation/results/), [model results](../research/execution/model-results.json) and [paper audit](../research/execution/paper-store-audit.json) support independent review.

## Historical Terminal V2 verification record

Latest full verification: **342 Python + 49 web + 39 gateway = 430 passed**, TypeScript/build and the integrated single-strategy browser workflow, 5 October 2026. See the [lifecycle verification record](single-strategy-verification.md) and `outputs/verification/lifecycle-full-final.log`.

The earlier audit verification below is retained as historical evidence (5 October 2026, Asia/Calcutta; raw timestamps use UTC). It includes the constant-weight cost correction and deterministic paper-event fixture. Its combined log remains `final-audit-20261005-passed.txt`; `python.xml` now records the latest lifecycle suite.

| Check | Result |
| --- | --- |
| Configured Python suite | **309 passed**, 4 warnings, 43.27 seconds in this run |
| Web quantitative/contract tests | **49 passed** |
| Gateway unit/runtime integration tests | **39 passed** |
| Total executed cases | **397 passed** across the three suites |
| TypeScript | `tsc --noEmit --incremental false` passed |
| Production build | `vinext build` passed; Sites manifest/plugin retained |
| Representative experiment | All 12 invariants passed; exact export replay passed |
| Python dependency consistency | `pip check`: no broken requirements |
| PowerShell scripts | Launcher and verification script parsed without errors |

The initial audit added 54 accounting/statistics/provenance cases. Five additional constant-weight cases now bring that group to 59; all passed in the full suite. Four independent cash/share cases reproduced the former undercharge before the fix. Two optional-ARIMA failure cases and three worker-lifecycle cases also passed. These counts include parameterized cases, not just function definitions.

An initial follow-up run passed 308 cases and failed one timing-dependent paper-event test when separate Windows clock reads returned the same tick. The fixture now controls time and explicitly verifies rejection at the signal-receipt timestamp before advancing. Production event-order rules were unchanged; the complete rerun passed all 309 cases. No failing check was removed or skipped.

## Reproduction and local evidence

Run `.\verify-v2.ps1` after dependency setup. It stops on failure and supplies a fresh checkout-local pytest temp directory. The complete script passed for the final revision. Its component commands are:

```powershell
# apps/engine, with a fresh checkout-local --basetemp
.\.venv\Scripts\python.exe -m pytest -o "addopts=-p no:cacheprovider --import-mode=importlib --ignore=evidence_tests/test_app.py" --junitxml=... --tb=short -q

# apps/web
node --test tests/quant.test.mjs tests/flagship-research.test.mjs tests/flagship-results.test.mjs tests/flagship-portfolio.test.mjs tests/performance-colors.test.mjs
node node_modules/typescript/bin/tsc --noEmit --incremental false
node node_modules/vinext/dist/cli.js build

# root: all apps/gateway/tests/*.test.mjs paths expanded by PowerShell
node --test <expanded gateway test paths>

# apps/engine
.\.venv\Scripts\python.exe -m scripts.representative_experiment
```

Latest combined log: `outputs/verification/final-audit-20261005-passed.txt`, with `python.xml` for the final suite. The preceding failure is retained in `final-audit-20261005.txt`. Original logs remain under `outputs/verification/{python.txt,web.txt,gateway.txt,typescript.txt,build.txt}`. The [latest experiment summary](evidence/representative-summary-20261005.json) records numerical outcomes, hashes, dependencies and checks; the [original summary](evidence/representative-summary.json) is preserved. Logs/generated state remain ignored.

## Qualifications

- The existing pytest configuration excludes `evidence_tests/test_app.py`, the historical Streamlit frontend test. It is not counted as passed. No new failures were skipped.
- Warnings: one Starlette/httpx deprecation and three pandas warnings from the deliberate nonfinite-skew test.
- Sandbox helper/Vite permissions required approved execution outside the sandbox. An inaccessible system pytest temp directory was replaced with fresh V2-local temporary storage.
- Windows Application Control initially blocked a Statsmodels native ARIMA dependency. Lazy import now isolates optional feature failures; no OS policy was disabled. Actual ARIMA numerical tests passed in the final suite, and simulated blocked-import tests verify visible failure without fabricated results.
- Separate copies of installed dependencies were reused and checked. Fresh network installation from both locks on another machine was not verified.
- Vinext warned that static analysis could not classify the root route; the build completed.
- [Browser verification](e2e-run.md) covered synthetic research submission, all 18 layers, result tabs, reload, export and replay with no JavaScript errors. It preceded the final constant-weight library fix; the latest API experiment and full tests cover that revision. This is not acceptance of every UI control, external broker/feed authentication, live orders, deployment, a fresh-machine install or repository-wide lint cleanliness. Provider integration tests use controlled fixtures.

[Version 1 verification](evidence/v1-verification.json) records the final comparison against the 347-file source baseline.

