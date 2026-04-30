# GitHub Repo Research

Date: 2026-04-30

Goal: identify open-source projects that can improve this bot without replacing
the corrected portfolio engine blindly.

## Priority Repos

| Repo | Use in this project | Decision |
|---|---|---|
| https://github.com/freqtrade/freqtrade | Lookahead/recursive-analysis ideas, dry-run discipline, futures backtest conventions | Study and port methodology checks, do not migrate bot now |
| https://github.com/ccxt/ccxt | Exchange abstraction already used | Keep as primary exchange layer |
| https://github.com/binance/binance-connector-python | Official Binance SDK, WebSocket/user stream/fill reconciliation | Candidate for live execution audit layer |
| https://github.com/hummingbot/hummingbot | Order lifecycle, order book, market making/execution guards | Use as execution-engine reference |
| https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api | Binance depth/bookTicker/forceOrder streams | Candidate for whale/liquidation watcher |
| https://github.com/polakowo/vectorbt | Fast robustness tests and parameter sweeps | Research layer only; current engine remains source of truth |
| https://github.com/ranaroussi/quantstats | Sharpe/Sortino/drawdown reports | Add later for reporting |
| https://github.com/dcajasn/Riskfolio-Lib | Portfolio risk contribution, CVaR, allocation analysis | Add later for SOL/ETH/BNB risk weights |
| https://github.com/skfolio/skfolio | sklearn-style portfolio optimization/risk management | Alternative to Riskfolio-Lib |
| https://github.com/TA-Lib/ta-lib-python | Verified indicators | Use for cross-checks if install friction is acceptable |
| https://github.com/xgboosted/pandas-ta-classic | Broad pandas-native indicators | Candidate for extra regime/orderflow indicators |
| https://github.com/guilyx/cryptopanic | CryptoPanic API client | Candidate for news watcher |
| https://github.com/man-c/pycoingecko | CoinGecko data wrapper | Candidate for market/news metadata |

## Integration Order

1. **Methodology checks**: copy the idea, not the framework. Add lookahead and
   recursive-indicator checks inspired by Freqtrade.
2. **Execution guards**: continue improving `execution_guard.py` with order book,
   spread, forceOrder/liquidation and depth data.
3. **Reporting**: add QuantStats-style metrics from `portfolio_equity.csv`.
4. **News/events**: connect CryptoPanic/CoinGecko/CoinMarketCal into
   `news_impact.py` and `event_calendar.csv`.
5. **Portfolio risk**: use Riskfolio-Lib or skfolio for correlation and risk
   contribution diagnostics before raising symbol count.

## Guardrails

- Do not paste external repo code without checking license.
- Do not replace the current engine until it reproduces current results.
- Any borrowed idea must pass this repo's portfolio walk-forward and Monte Carlo.
- News/social repos are allowed to reduce risk or add context; they must not
  directly open positions without price/volume confirmation.
