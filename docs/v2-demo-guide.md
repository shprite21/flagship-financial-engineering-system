# Q V2 — five-minute research walkthrough

Use the local app after `start-q21.ps1`. It opens Research projects. For the canonical browser example, run `apps/web/scripts/project-e2e.cjs` against a local preview with an installed Playwright runtime and Edge. Each run creates a clearly named **SYNTHETIC lifecycle browser acceptance** project and preserves the prior attempts. See the [completion record](v2-finalization.md) for the latest verified evidence locations.

Prepare the saved example before an interview so compute time does not consume the walkthrough. Open the project by its title. These prices are generated fixtures, not market performance.

## 0:00–0:45 — Question and lineage

Show THESIS: a falsifiable fixed momentum hypothesis, mechanism, failure conditions and acceptance/rejection criteria. Explain that edits create immutable revisions. Show DATA: the exact fingerprint, 720 development observations and 180 reserved observations. Identical bytes cannot be recaptured with a different holdout boundary. Public history is not certified untouched data.

## 0:45–1:30 — Signal, portfolio and accounting

Show SIGNAL: fixed 63-bar momentum, equal weighting in the browser example, weekly rebalance, costs, position/exposure limits and regime conditioning off. Explain lagged fractional close-to-close research versus the separate whole-share cash/volume execution stress. The account models are deliberately disclosed instead of mixed.

## 1:30–2:20 — Retain alternatives and negative evidence

Show EXPERIMENTS: both the 63- and 80-bar trials remain. The 80-bar neighbor is explicitly rejected for promotion because it was not the prespecified candidate; it is not deleted.

Open COMPARE and select both. Explain the matching fingerprints, dates, account convention and source. Show return, drawdown, turnover, costs and walk-forward evidence together. Curves use fixed colors; losses remain red in the table. Q neither picks a winner nor infers statistical significance from this comparison.

## 2:20–3:15 — Validation and uncertainty

Open VALIDATION/ROBUSTNESS. The canonical example reports WARN overall, including unavailable DSR without a defensible effective-trial/IID assumption. Explain HAC dependence correction, seeded block bootstrap, recorded-family BY adjustment and CSCV/PBO as conditional diagnostics. Eighteen reporting layers are not eighteen independent tests. Cost stress uses full development history; headline metrics exclude warmup.

## 3:15–4:10 — OOS, freeze and prospective separation

Show the permanent OOS reveal event, the retained result even if negative, and the frozen StrategyVersionID. Do not reveal a fresh study merely for a demonstration. Show FORWARD: an empty protocol, **zero observations**, no broker verification. Synthetic promotion and fabricated forward marks are blocked. Explain that later strategy edits cannot change a frozen deployment.

Open MONITOR: historical, walk-forward, reserved OOS and prospective columns are separate. Unavailable forward metrics do not become zero or a pass. Alerts request review; they do not place orders.

## 4:10–5:00 — Reproduction and engineering

Open PAPER and download the report and reproducibility ZIP. Explain immutable evidence versus mutable job bookkeeping, one bounded shared research queue, explicit failure retention, source/data/dependency checks, and replay without executing unreviewed archived code.

From `apps/engine`:

```powershell
.\.venv\Scripts\python.exe -m research.projects.replay C:\path\to\research-project.zip
```

End by naming the actual limitations: selected-universe history, modeled impact and account conventions, unknown external research/search history, no independently certified untouched OOS, and no prospective track record from an empty registration. Live execution remains disabled.
