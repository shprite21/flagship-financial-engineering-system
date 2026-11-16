# Q V2 live end-to-end run — 5 October 2026

The newer [single-strategy lifecycle browser acceptance](single-strategy-verification.md) verifies the integrated project workflow and both export replays after 430 test cases passed. The earlier portfolio-research run below remains preserved as its original evidence.

The application was launched using start-q21.ps1 and remains running at http://localhost:5273, with its gateway on 5274. Process command lines were verified to point to C:\quant\terminal-v2.

## Passed checks

- Complete verify-v2.ps1: 304 Python, 49 web and 39 gateway cases; TypeScript and production build passed.
- Repeated fixed synthetic research experiment: all 12 invariants passed, including exact replay.
- Live HTTP smoke: health, directory catalogue, validation errors, same-origin restrictions and missing-provider-key behavior passed.
- Isolated headless Edge browser: rendered home/research screens, submitted a synthetic study through the actual UI and gateway, and completed all 18 Survival layers.
- Research overview, Alpha sleeves, Validation, Portfolio & risk and Experiment book opened without JavaScript errors.
- Saved experiment reloaded after a full page reload; export returned HTTP 200.
- The browser-created export reproduced exactly through research.survival.replay.

Saved study: **SYNTHETIC E2E browser verification**

Experiment: `20261004T203103Z-11f1dbf2`

Survival: `13344357460f39c2fcc9a5867583b436d961a3672043a6dc2e3316bc659b7591`

Survival outcome: **2 PASS, 14 WARN, 0 FAIL, 2 unavailable**, not investment approval. The browser used default lookbacks, so this is a separate study from the fixed representative protocol. Synthetic promotion remains blocked; live eligibility remains false.

## Evidence

Local outputs under `outputs/verification`:

- `e2e-20261005.txt`: combined test/build log.
- `browser-e2e.json`: browser run IDs, tab coverage, errors and outcome.
- `browser-survival-export.zip`: completed export, exact replay verified.
- `e2e-home.png`, `e2e-research-overview.png`, `e2e-survival-complete.png` and tab screenshots.

Browser automation used installed Edge because the built-in browser tool failed with the sandbox setup-helper error and Playwright's separate Chromium download was absent. No browser installation or OS policy change was made. The app was left running for the user. This was a synthetic system test, not broker-authenticated trading or verification of every UI control.

## Final accounting follow-up

The later constant-weight library correction added five independent/edge cases. Final verification passed **309 Python + 49 web + 39 gateway = 397 cases**, TypeScript and the production build. A new fixed API experiment passed all 12 invariants and exact replay; see the [updated verification record](verification.md). The browser study above remains its original saved artifact and was not overwritten or relabeled as a later revision.

The final V2 launcher was started again on 5 October; gateway, Python and web process paths were verified within this checkout. The live API smoke passed. An Edge browser reopened the preserved synthetic study on the fresh runtime without JavaScript errors; `outputs/verification/final-runtime.json` and `final-runtime.png` record that check. The application is available at `http://localhost:5273` while the local launcher remains running.
