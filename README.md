# Flagship Financial Engineering System

A financial engineering terminal for testing equity signals, pricing and hedging derivatives, and measuring portfolio risk. Terminal V2 supplies the React workbench, Python research engine, TypeScript backtester, portfolio construction, experiment registry and prospective paper ledger. Four research modules share this infrastructure and retain their own hypotheses, models, accounting conventions and tests.

## Research results

| Module | Comparison | Measured finding |
| --- | --- | --- |
| [Regime-Switching Trading System](docs/modules/regime.md) | Filtered three-state HMM against equal strategy budgets, 2021–2025 | Net Sharpe −0.14 vs −0.50. HMM CAGR −0.85%, maximum drawdown −11.99%, annual traded notional 25.99× equity. |
| [Cointegration-Based Statistical Arbitrage](docs/modules/stat-arb.md) | Nested spread selection against fixed thresholds, 2021–2025 | KO/PEP failed the formation screen in all ten folds. Both policies stayed in cash. Sharpe is undefined. |
| [Derivatives Pricing & Market Making](docs/modules/derivatives.md) | Delta hedge against unhedged inventory across 64 paired synthetic paths | Mean residual delta RMSE fell from 482.57 to 219.99 shares. Mean marked net P&L fell from −$1,458 to −$2,836. |
| [Multi-Asset Risk Simulation](docs/modules/risk.md) | Trailing one-day 95% VaR against 1,508 subsequent sessions, 2020–2025 | 75 breaches (4.97%). On breach days, realized losses averaged $2,461 vs forecast ES of $1,779 per $100,000. |

The two strategy studies use 1,255 historical sessions from January 4, 2021 through December 31, 2025. The HMM Sharpe difference was +0.36 with a paired 97.5% block-bootstrap interval of [−0.15, +0.86]. The 5 bp case includes 2 bp commission and 3 bp slippage per traded dollar. Rerunning at zero execution cost raised HMM Sharpe to +0.12. Doubling execution cost reduced it to −0.39. Borrow remained 3% annually. These retrospective experiments leave a tradable edge unconfirmed. [Methods, cost reruns and daily ledgers](research/validation/README.md)

**Forward trading evidence.** The November 16, 2026 audit found two demo registrations, zero forward signals or observations, and zero deployments in the two retained local paper stores. No broker receipt was available. The terminal has a prospective simulator and a read-only Alpaca paper receipt exporter. Future track-record claims require dated fills attributable to a frozen strategy. [Execution evidence](research/execution/README.md) · [Store audit](research/execution/paper-store-audit.json)

## Run the terminal

Use Windows, Node.js 24+ with npm, and Python 3.12. From a fresh checkout in PowerShell:

```powershell
.\setup-flagship.ps1 -Python python
Push-Location apps/web
npm run install:ci
Pop-Location
.\start-flagship.ps1
```

Open [the local terminal](http://127.0.0.1:5273/). **Research evidence** compares saved results offline. Use **Open workbench** under a module to configure a new experiment. For observed-price studies, import your own dated history or select a supported provider. Synthetic histories are explicitly labeled. The prospective runner uses a separately configured feed, and live order submission is disabled.

**Research projects** records hypotheses, trials, data partitions and candidate freezes. **Portfolio engineering** and **Allocation replay** handle portfolio construction. The advanced research workbench includes a constrained efficient frontier and out-of-sample ARIMA evaluation against a naive forecast. **Company intelligence** and **Economy lab** retain report retrieval and the native agent-based simulation. [Architecture](docs/implementation.md) · [Single-strategy lifecycle](docs/single-strategy-lifecycle.md) · [Portfolio modeling](apps/engine/qresearch/modeling.py)

## Verify or extend a study

```powershell
python research/validation/verify.py
node --test research/execution/paper-receipt.test.mjs
.\verify-v2.ps1
```

The first command independently recomputes the published historical metrics from the included derived daily ledger and checks the source fingerprints. Full price-to-result replay requires the exact private adjusted-close panel. The model studies include the data hash, parameters, code and independent checks. [Strategy replay](research/validation/README.md#reproduction) · [Derivatives and risk replay](research/execution/README.md#reproduce-the-measurements)

Read the [source map](docs/source-map.md) for the migration from the original GitHub projects and the [supplemental labs](research/labs/README.md) for the factor, forecasting, derivatives, stress and company-research tools. Historical migration records use the earlier product name. Compatibility identifiers keep saved artifacts and replay tools readable.

