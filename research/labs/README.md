# Supplemental research labs

The flagship terminal serves the four primary workbenches through its Python engine and local gateway. These six labs retain additional experiments from the source projects. Run each lab from its own directory in a dedicated Python environment. The index and factor packages use different libraries with overlapping module names. [Flagship studies](../validation/README.md) · [Risk and execution evidence](../execution/README.md)

| Lab | Relationship to the terminal | Run from the linked directory |
| --- | --- | --- |
| [Factor lab](factor-lab/) | Cross-sectional momentum, value, quality, low volatility, factor IC and portfolio constraints. Its demo generates seeded equity and fundamental panels. | Install `requirements.txt`, then `python main.py --periods 504`. |
| [NIFTY trend](nifty-trend/) | Logistic regression, random forest and XGBoost predict the next NIFTY 50 close direction. The download requires Yahoo access. Classification scores measure forecasts. | Install `requirements.txt`, run `python market_regime_detection.py`, then `python launch_dashboard.py`. |
| [Index derivatives](index-derivatives/) | Six source notebooks explore NIFTY/BANKNIFTY directional exposure, regime labels and option strategy selection. The inherited notebook sequence fits its regime model on the full history before the signal study. Its five-session targets can overlap fold boundaries. Treat the notebook outputs as exploratory. Use the flagship derivatives workbench for dealer inventory and hedging studies. | Install `requirements.txt`. Run `python -m pytest tests` for numerical fixtures or `python -m jupyter lab notebooks` to run the numbered notebooks in order with market-data access. |
| [Portfolio stress](portfolio-stress/) | Four-sleeve covariance stresses, loss quantiles and path drawdowns. The CLI accepts a configurable input history. The included generator creates fictional sleeve returns. | `python -m pip install -e .`, then `python data/generate_sample_data.py` and `python -m risk_engine.main --config config/default_config.json`. |
| [Company intelligence](company-intelligence/) | Adds the source dashboard's company comparison, cited filings, news and report workflows to the integrated terminal's report indexing and search. Includes the source MIT license and three labeled, archived AI examples. Retrieval and generation need their configured providers. | Install `requirements.txt`, then `python -m streamlit run app.py`. Provider credentials belong in the lab's local configuration. |
| [Monte Carlo option pricing](cuda-pricing/) | CPU and optional CUDA simulation of discounted European call payoffs with an analytic Black–Scholes benchmark. GPU builds need the CUDA toolkit, driver and compatible hardware. | From the lab, run the CMake commands below. |

```powershell
cmake -S . -B "$env:TEMP/flagship-mc-cpu" -DMC_ENABLE_CUDA=OFF
cmake --build "$env:TEMP/flagship-mc-cpu" --config Release
ctest --test-dir "$env:TEMP/flagship-mc-cpu" -C Release --output-on-failure
```

## Source revisions

The financial-engineering imports use commit `6c21f24c370ffe1d5de208f22039964354b21f13`. The factor module is the `systematic-equities-research-lab` package retained in project 01. Project 01's regime and Shprite equity platform also feed the flagship's main engine. Project 05 supplies the integrated Terminal V2 implementation. [Source portfolio at the imported revision](https://github.com/shprite21/financial-engineering/tree/6c21f24c370ffe1d5de208f22039964354b21f13)

| Directory | Source within the financial-engineering revision |
| --- | --- |
| `factor-lab` | `01-Regime-Aware-Systematic-Equities-Trading-Platform/factor-lab` |
| `nifty-trend` | Classifier and dashboard in `02-Statistical-Arbitrage-and-Signal-Research` |
| `index-derivatives` | Index workflow in `03-Derivatives-Pricing-and-Market-Microstructure` |
| `portfolio-stress` | Risk CLI in `04-Portfolio-Risk-and-Quantitative-Modeling` |

The company dashboard comes from `shprite21/competitive-market-intelligence-dashboard` at `ee5612997e2370ed6058a2664a2446521332a7ac`. The CUDA project comes from the author's local C++/CUDA work. Its nine source, build and test files have individual SHA-256 fingerprints. [Company dashboard revision](https://github.com/shprite21/competitive-market-intelligence-dashboard/tree/ee5612997e2370ed6058a2664a2446521332a7ac) · [CUDA fingerprints](cuda-pricing/source-hashes.json)

The six index notebooks retain the original cell sources with execution counts and outputs cleared. The NIFTY classifier rejects missing history, calculates its volatility threshold using observations through the signal close and purges the boundary observation for its next-close label. Model selection ranks training-fold mean ROC-AUC. The held-out comparison reports the performance of that selection. These fixes apply to newly computed studies. [NIFTY implementation](nifty-trend/market_regime_detection.py) · [Future-data perturbation test](nifty-trend/test_chronology.py)

## Verification

The 504-session synthetic factor example ran. The factor suite passed six tests, the index suite passed six, and the portfolio stress suite passed 58, including an end-to-end report built from generated data. The NIFTY future-data perturbation and label-boundary check passed. The CPU Monte Carlo implementation built under MSVC 19.44 and passed all three CTest checks. These measurements exercise the retained software. Performance results used by the terminal and résumé come from the separately documented flagship studies.

The company dashboard passed 106 tests covering research agents, filing retrieval and comparisons, market data, launch configuration and saved history. The full suite stopped during collection because Windows Application Control blocked a fontTools native extension needed by its optional PDF exporter. Live provider calls and CUDA execution were outside these offline checks.
