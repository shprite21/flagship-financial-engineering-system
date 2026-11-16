# Native economy lab

Open **Economy lab** in Q to run the original C++ closed-cash model or a measured CPU population study. Q retains the native source, original C++ invariant tests, CUDA reference, CMake build and timing-analysis reference under `apps/engine/qmodules/native`. Its origin manifest records the source hashes; the original project stays unchanged.

The adapter uses Q's existing one-worker bounded research queue. It compiles the frozen source snapshot with the pinned Zig C++ compiler, C++17, O3 and `-ffp-contract=off`. It records compiler/flags, binary and source hashes and host identity. Compilation and native execution have time limits and cooperative cancellation. Subprocesses receive OS/runtime variables but no provider credentials. There is no Python substitute for the native economy.

## Economic conventions

Households have seeded heterogeneous initial cash and consumption propensities. Firms have seeded fixed productivity and initial cash. Each household belongs to a fixed local firm. Firms hire no more than their cash can fund; jobs rotate across assigned households. Production is productivity times employment. Realized household spending is limited by local supply and allocated proportionally to desired spending.

Wages transfer firm cash to households; purchases transfer household cash to firms. Household saving is income minus consumption. Unspent cash remains available, and unsold output perishes. Prices stay fixed. This is a computational model, not empirical GDP, market prices or investment returns. Credit, banks, investment, dividends and asset-market trading are absent.

Every new result checks:

- finite complete rows and the expected step sequence;
- total household plus firm cash against initial cash;
- changes in household cash against reported saving;
- reported total cash against reconstructed balances;
- nonnegative aggregate balances, spending and output;
- whole-number employment within the population and matching unemployment;
- constant configured price and consumption within supply value;
- final household histogram population reconciliation.

Cash checks use `1e-8 + 1e-10 * abs(initial_money)`. The retained C++ tests additionally inspect each household/firm, wage and revenue transfers, one-agent hand calculations, edge populations, zero liquidity and seed repeatability. Python integration tests independently reconstruct the one-household transfers, inspect all exported rows, test corrupted outputs, zero cash and replay.

## Scaling studies

Each population has one saved warmup and two to five measured repetitions. Every attempt retains configuration, complete trajectory, native result and invariant checks. Medians exclude warmups; min/max and seeded 10,000-resample percentile intervals describe runtime variability on this host. Small repeat counts give poor interval resolution. These intervals are not economic uncertainty estimates.

Every completed measurement is also saved as an independent `economy_observation` before the next attempt starts, so a later failure or cancellation cannot erase it. Failed/cancelled module jobs retain their submitted configuration and a reference to the immutable source snapshot. PDF/text import jobs retain content hashes instead of repeating large source payloads in each status response.

Increasing population while holding firm count fixed changes market sizes and liquidity per household. A scaling study is not a controlled study of economic population effects. Q limits individual runs to 20 million household-timestep updates and benchmark batches to 60 million, including warmups, within the shared scheduler.

## Reproducibility and scope

Results and exports retain configuration, calculation source, dependency identity, native build metadata and complete observations. `python -m qmodules.replay EXPORT.json` requires matching source/dependency fingerprints and exact numerical output. Native timer fields are excluded; compiler, flags, platform and source identity remain checked. The verifier reports whether the rebuilt native binary matches the saved binary. Exact native binary identity can vary across build locations.

CUDA code remains preserved but unverified on this host. Q exposes the CPU implementation only. GPU speedup, the source project's planned financial-market phase, production execution and empirical macroeconomic claims are not fabricated or promoted by this consolidation.
