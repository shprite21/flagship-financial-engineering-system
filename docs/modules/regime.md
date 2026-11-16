# Regime-Switching Trading System

Does a three-state Gaussian hidden Markov model improve allocation across momentum, mean reversion and statistical arbitrage? The control assigns equal budgets to the same sleeves. The candidate fits on past observations, filters state probabilities forward and sends targets to the next eligible close. Both policies start with $100,000 and use the same cash, borrow, collateral and integer-share rules. [HMM implementation](../../apps/engine/qresearch/regimes.py) · [Account accounting](../../apps/engine/qresearch/equity_account.py)

| January 4, 2021 through December 31, 2025 | Static budgets | HMM allocation |
| --- | ---: | ---: |
| Net annualized Sharpe | −0.50 | −0.14 |
| Net CAGR | −2.21% | −0.85% |
| Maximum drawdown | −15.86% | −11.99% |
| Annual traded notional / equity | 26.96× | 25.99× |

The HMM lost money over 1,255 sessions. At 0, 5 and 10 bp one-way costs, rerunning the HMM and account produced Sharpe of +0.12, −0.14 and −0.39. Short borrow stayed at 3% per year. The paired 97.5% bootstrap interval for the 5 bp Sharpe improvement was −0.15 to +0.86. These results leave the allocation edge unconfirmed. The six surviving stocks and revised price history limit generalization. [Protocol, cost sensitivity and reproduction](../../research/validation/README.md) · [Dated ledger](../../research/validation/results/daily.csv)

Open **Research evidence → Regime-switching trading → Open workbench**. Select or import a multi-asset history and run the HMM allocation. The study records refit dates, convergence, regime attribution and both account paths. [Numerical tests](../../apps/engine/tests/test_qresearch_strategies.py)
