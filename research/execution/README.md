# Derivatives, portfolio risk and execution evidence

## Derivatives pricing and market making

**Hypothesis.** Next-event delta hedging reduces the market maker's residual delta exposure. For 64 paired seeds (0–63), both arms started with $100,000, used the same simulated underlying and customer-flow seeds, and posted quotes before each subsequent event. The control carried its option inventory unhedged. The treatment targeted a whole-share hedge once residual delta exceeded 15 shares. The primary endpoint was the mean across paths of within-path delta RMSE, measured in shares. Each path spanned 780 events over ten modeled trading days. [Pricing and Greeks](../../apps/engine/qresearch/options.py) · [Market-making simulator](../../apps/engine/qresearch/option_simulation.py)

| Mean across 64 synthetic paths | Unhedged | Delta hedged |
| --- | ---: | ---: |
| Residual delta RMSE, shares | 482.57 | 219.99 |
| Prior holdings' per-event mark change RMSE, USD | 75.86 | 34.81 |
| Terminal marked net P&L, USD | -1,457.69 | -2,836.30 |
| Maximum drawdown | -3.28% | -3.59% |
| Stock hedge fee, USD | 0.00 | 508.65 |
| Stock hedge slippage, USD | 0.00 | 1,017.29 |

Hedging reduced residual delta RMSE by 262.58 shares. A paired percentile bootstrap over the 64 seeds gave a 95% interval of 241.52–283.42 shares of reduction. Hedge fees and slippage averaged $1,525.94 per path, and the hedged account lost more money. Collateral constraints and inventory-dependent quotes can change which customer orders each arm accepts. The interval describes Monte Carlo variability conditional on this order-flow model. Open positions were marked at the final modeled event. Historical order-book data, queue dynamics and closing costs would be needed to evaluate executable market-making returns.

Across 30 spot, maturity and volatility combinations, maximum absolute put–call parity error was 1.42 × 10⁻¹⁴ price units. Central finite differences on call prices gave maximum delta and gamma errors of 6.11 × 10⁻⁸ and 4.04 × 10⁻⁸ using a $0.01 spot increment. [Measured results](model-results.json)

## Multi-asset risk simulation

**Hypothesis.** A trailing Gaussian covariance model provides 95% one-session VaR coverage for an equal-dollar portfolio of MSFT, JPM, XOM, JNJ and PG. We estimated mean log returns and covariance using the previous 252 sessions and generated 10,000 correlated paths per forecast. Each evaluation day started with $100,000, divided equally across the five stocks. Risk forecasts used common random numbers, and the first and last forecasts were independently replayed through the terminal's full one-day simulation. [Risk engine](../../apps/engine/qresearch/risk_simulation.py)

From **2020-01-02 through 2025-12-31**, realized losses exceeded 95% VaR on **75 of 1,508 sessions (4.97%)**. The exact binomial 95% interval for the rate was 3.93–6.19% under independent breaches. The unconditional rate was close to its 5% target. Loss severity was less well captured. On breach dates, mean realized loss was **$2,461**, compared with mean predicted expected shortfall of **$1,779**. This descriptive comparison does not adjust for serially dependent breaches.

The final 21-session projection used the last 252 observed returns through 2025-12-31. Starting exposures were held throughout each path. Each scenario used identical shocks and 10,000 paths.

| Scenario | 95% VaR loss | Expected shortfall | Median path maximum drawdown |
| --- | ---: | ---: | ---: |
| Fitted covariance | $4,561 | $6,139 | -2.85% |
| Twice the fitted volatility | $9,953 | $12,875 | -5.99% |
| Correlations blended 90% toward +1 | $8,131 | $10,434 | -4.97% |
| Zero cross-asset correlations | $3,032 | $4,254 | -2.03% |

The fixed five-name universe contains surviving US stocks. Prices are revised, dividend- and split-adjusted end-of-day marks. These risk forecasts omit execution, fees and slippage. The six-year evaluation is a retrospective chronological holdout. The stress projections cover hypothetical future paths.

### Reproduce the measurements

From the repository root in the engine's Python environment, supply the private historical panel. The reference input is the original 25-symbol adjusted-close CSV (4,024 rows) in the author's historical study, retrieved from the Yahoo chart endpoint on 2026-11-07. It spans 2010-01-04 through 2025-12-31. The runner reads the date and the five named stocks. A data owner can supply an equivalent CSV with those six columns. Vendor revisions, rounding or missing sessions may change results. The checked-in JSON records the full reference input's SHA-256. [Runner](measure_models.py) · [Machine-readable measurements and parameters](model-results.json)

```powershell
python research/execution/measure_models.py --prices "<private data directory>/processed/adj_close.csv" --out model-replay.json
```

## Forward paper evidence

On 2026-11-16, both retained terminal paper stores had **zero deployments and zero events**. The Terminal V2 research registry held **two demonstration registrations, zero signals and zero forward observations**. Both frozen requests used demo data. The Terminal V2 Indian-market journal contained zero events. No broker receipt was available at audit time. Strategy-attributable forward performance remains unverified. [Timestamped store counts](paper-store-audit.json)

The integrated **Deployments** workflow can run a frozen strategy prospectively with an explicitly configured feed and records modeled fills in its private hash-linked ledger. Its export verifies the saved inputs, event chain and replayed account checkpoint. [Paper runner, activation and ledger export](../../docs/paper-trading.md) · [Ledger implementation](../../apps/engine/paper/storage.py)

For broker-side execution evidence, the read-only receipt command connects directly to the existing Alpaca paper adapter using backend environment variables `ALPACA_PAPER_API_KEY` and `ALPACA_PAPER_SECRET_KEY`. It reports the number of completed orders, other orders with executed quantity, the observation time and completed-order date range. A successful call examines up to the latest 100 account orders. Attribution requires a subsequent match to the frozen strategy's own order records. A local receipt is a summary someone with account access can rerun. [Receipt implementation](paper-receipt.mjs) · [Gateway adapter](../../apps/gateway/alpaca-paper.mjs)

```powershell
node research/execution/paper-receipt.mjs
node --test research/execution/paper-receipt.test.mjs
python research/execution/audit_paper_stores.py --terminal-v2-data "<closed Terminal V2 .data directory>" --predecessor-data "<closed predecessor .data directory>"
```
