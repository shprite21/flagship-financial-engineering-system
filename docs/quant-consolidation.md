# Q project consolidation

The active implementation lives in `C:/quant/terminal-v2`. Original projects stay read-only references. This consolidation covers source capabilities, not credentials, historical results, or live execution permissions.

## Source review — 7 October 2026

| Source | Findings | Q destination |
| --- | --- | --- |
| `terminal` | Previous Q workspace, including portfolio, Evidence, derivatives, HMM and basket integrations | Preserve V2 improvements; compare source snapshots before importing missing behavior |
| `projects/Regime-Aware-Systematic-Equities-Trading-Platform` | Modular signals, allocation, research and analytics already adapted into Q | Existing engine and portfolio research workflow |
| `projects/systematic swing trading bot/backtester` | Strict daily research, bar lab and synthetic market making already adapted into Q | Existing Evidence actions and immutable artifact library |
| `projects/Parallel-Agent-Based-Economic-Financial-Market-Simulator` | Native C++ closed-cash economy; CUDA source is unverified; financial-market phase is planned | Native economy research action using Q's bounded queue and artifact store |
| `projects/Competitive-Market-Intelligence-System` | Company-report selection, PDF indexing, retrieval and optional external model/news services | Company intelligence research with frozen documents, page citations and explicit provider state |
| `projects/python/1.ipynb` | One code cell importing pandas; no independent model or calculation | Inventory only; pandas already present |

## Acceptance

- Preserve source projects and record their file hashes.
- Integrate new calculations through the existing bounded research queue.
- Freeze inputs, source identity and complete results; expose failures honestly.
- Keep the native economy synthetic and separate from strategy accounting.
- Treat report contents as evidence, never instructions; cite company, report and page.
- Keep external AI/news unavailable unless configured and successfully called.
- Run native accounting checks, integration tests, existing Python/web/gateway tests, TypeScript and production build.

## Implemented consolidation

Q now has **Company intelligence** and **Economy lab** entries in its existing navigation. Both reuse the private engine, the bounded research executor, immutable artifacts, common library/export controls and Q's interface. There is no second frontend, scheduler or broker service. The eight new actions cover native simulation/scaling, report import/search, local semantic index/search, cited local AI answers and actual-provider news retrieval.

The [company intelligence guide](company-intelligence.md) explains source-page citations, immutable PDF imports, deterministic lexical ranking, optional local embeddings and provider boundaries. The [economy methodology](economy-lab.md) documents the original C++ model, independent conservation checks, cancellation, measured timings, saved warmups and bootstrap intervals.

The regime platform and Evidence are already integrated through 134 recorded source migrations; every original source still matches its import-time hash and every destination exists. V2's subsequent numerical and lifecycle improvements are preserved. All V1 product source files in the audit are present in V2; three historical V1 acceptance/measurement documents remain in their original location. The original product specification was restored as an ignored historical reference. It is not a demand to implement its future roadmap.

The expanded [source inventory](quant-source-audit.json) covers **572 source files**: 347 from terminal V1, 119 from the regime platform, 49 from the swing/Evidence project, 44 from the native simulator, 12 from company intelligence and one notebook. Data-provider Python packages are included; runtime datasets, dependency installations and credentials are excluded. Original source hashes and all six source PDF hashes remained unchanged. The native adapter preserves seven original native/build/test/analysis files with a separate origin manifest.

Six cached company PDFs were imported into Q's private immutable store: **1,089 pages** from Reliance Industries, Adani Enterprises and Swiggy. Their supplied metadata remains unverified; original bytes and page-level evidence are retained. No existing strategy/result snapshots were edited, and no source-project account, broker credential or active deployment was moved.

## Verification — 7–8 October 2026

[Machine-readable acceptance](evidence/quant-consolidation-verification.json) records the source inventory, tests, live artifact identities, replay and browser checks.

- Full verification: **372 Python tests, 67 web tests and 39 gateway tests passed**. TypeScript checking and the production build passed. The required standalone `node --test tests/quant.test.mjs` command also passed all 16 tests; those are already included in the 67 web tests. The final child-measurement/job linkage was additionally checked in the focused module and private-API tests.
- The new tests exercise original native C++ accounting/hand calculations, Python transfer reconstruction, zero cash, malformed configurations/results, cancellation, timing warmup exclusion, retention of completed measurements after a later failure, frozen failed-job requests, report/source tampering, PDF parsing, deterministic cross-process search, immutable semantic vectors, model drift, invalid vectors, citation validation and private API access. Provider fixtures are explicitly test doubles.
- Browser acceptance submitted a real local report search and a native CPU simulation through Q. Six page citations appeared, the linked original PDF returned HTTP 200, four economy charts rendered, and no browser page errors were recorded. The search field's accessible label was repaired after the browser check exposed it.
- The live gateway's exported report search and native economy result replayed successfully against the current source/dependency fingerprints. A separate live CPU scaling study completed six native attempts, including two excluded warmups. Every attempt passed conservation checks and retained an independent observation linked to its parent job and frozen source record.
- Live health reports `research_only`, one compute worker and `liveOrderSubmission: false`. The Sites hosting manifest and Vite Sites plugin remain intact. The integration runs locally; the Python runtime and private reports were not published to Sites.

One full-suite attempt hit Windows Application Control when first launching the newly compiled native test executable. The exact same executable subsequently passed without binary or security-setting changes, and the subsequent complete suite passed. No security control was disabled or bypassed.

The final audit rechecked all 572 original source files, the 134 existing migration records, seven preserved native files, six original PDFs and both Sites configuration files. No original source or PDF changes were found.

## Explicit limits

Ollama was unavailable during the local readiness check, and optional model/news variables were unconfigured. Their adapters, failure gates and deterministic fixture contracts are implemented and tested; successful live AI generation, embedding generation or authenticated news retrieval is **not claimed**. Lexical report search and native CPU calculations were verified end to end without them.

CUDA runtime validation and the native source project's planned financial-market phase remain unimplemented/unverified source-project scope. Historical README performance statements are not new Q results. Production risk, compliance, settlement, broker reconciliation, approvals and live order submission remain outside this consolidation; live execution stays disabled.
