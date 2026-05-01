# Binance Futures Trading Bot

A 4-hour Donchian breakout trend-following bot for Binance Futures.

> **Status:** Research and testing phase. The backtest infrastructure has matured, but the bot is **not** ready for live trading. Start with [docs/MULTI_SYMBOL.md](docs/MULTI_SYMBOL.md) and [docs/WALK_FORWARD.md](docs/WALK_FORWARD.md) for the latest decision context.

## Quick Overview

| Item | Value |
|---|---|
| Target capital | 1,000 USDT |
| Primary timeframe | 4 hours |
| Higher timeframe filter | 1D EMA50; weekly trend context calculated but not enforced |
| Leverage | 10x testnet candidate |
| Risk per trade | 4% base on first open position, correlation-aware after that |
| Primary signal | Donchian breakout |
| Filters | Volume, ADX, RSI, 1D trend, calendar/news risk, volume profile, candlestick context, futures flow context |
| Exits | ATR initial SL, dynamic trailing SL, Donchian exit |
| Mature-bot add-ons | Protection layer, exit ladder, pair universe, TWAP planner, executor contract, bias audit are present but passive by default |

## Strategy

**Entry logic:**

1. The 4H close breaks the prior Donchian channel.
2. The bar volume is above a multiple of the 20-bar moving average.
3. ADX is above the trend-strength threshold.
4. RSI is not in extreme overbought/oversold territory.
5. The 1D trend filter confirms the same direction.
6. Candlestick/price-action patterns and futures-flow context can adjust risk sizing; they do not create standalone trades.

**Exit logic:**

- Initial stop-loss: ATR-based.
- Trailing stop: locks in a portion of the gains.
- Early exit: a shorter Donchian channel breaks in the opposite direction.

## Current Findings

- The current candidate is the DOGE/LINK/TRX `growth_70_compound` portfolio profile.
- Latest 3-year candidate sweep/backtest: about `+124.21% CAGR` with `5.05%` peak drawdown.
- Candidate portfolio walk-forward: fixed growth profile is positive in `7/7` test periods, with `20.12%` average test return and `5.25%` worst test return.
- Candidate Monte Carlo: block bootstrap ending-equity p05 is `6191.14` from `1000` start, ending-equity loss probability is `0%`, and peak-DD p95 is `6.25%`.
- Timeframe research: [docs/TIMEFRAME_SWEEP.md](docs/TIMEFRAME_SWEEP.md) shows 1h is not robust after horizon scaling, while 2h is a stronger but higher-drawdown candidate than the current 4h default.
- Verdict: testnet/paper only. Live trading remains blocked until real fills, order-book guard logs, futures-flow logs, and news-event controls are reviewed.

## Files

```text
config.py                    Parameters
data.py                      Live data and exchange queries
indicators.py                ATR, RSI, ADX, Donchian, daily trend
strategy.py                  Signal and exit rules
risk.py                      Position size and SL/TP calculation
pattern_signals.py           Rule-based candlestick/price-action context
flow_data.py                 Futures flow context for live/testnet risk decisions
protections.py               Passive mature-bot protection checks
exit_ladder.py               Passive partial-TP/breakeven plan helper
pair_universe.py             Passive dynamic pairlist/liquidity/volatility scoring
twap_execution.py            Passive TWAP slice planner
trade_executor.py            Passive lifecycle contract for future execution refactor
bias_audit.py                Lookahead/recursive indicator stability audit
ops_status.py                Local paper/testnet status report
paper_report.py              Detailed paper decision/equity/error report
paper_runtime.py             Tagged paper/shadow runtime isolation helpers
mature_bot_compare.py        Side-by-side add-on validation
portfolio_candidate_sweep.py Search better symbol combinations
timeframe_sweep.py           Compare 1h/2h/4h with raw and scaled indicator horizons
paper_runner.py              No-order paper telemetry and virtual portfolio runner
testnet_fill_probe.py        Explicitly approved testnet fill/slippage probe
order_manager.py             Order placement, SL update, position close
bot.py                       Multi-symbol portfolio bot loop (testnet/live)
backtest.py                  Single-symbol backtest
optimize.py                  Parameter sweep
walk_forward.py              Single-symbol walk-forward
multi_symbol_backtest.py     Multi-symbol straight backtest
multi_symbol_walk_forward.py Multi-symbol walk-forward
monte_carlo.py               Monte Carlo trade-shuffle
docs/                        Review and result reports
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
python backtest.py
python walk_forward.py
python multi_symbol_backtest.py
python multi_symbol_walk_forward.py
python monte_carlo.py --trades backtest_results.csv
python bias_audit.py --symbol DOGE/USDT --years 1 --sample-step 96
python bias_audit.py --symbol LINK/USDT --years 1 --sample-step 96
python bias_audit.py --symbol TRX/USDT --years 1 --sample-step 96
python mature_bot_compare.py --years 3
python portfolio_candidate_sweep.py --years 3 --min-size 3 --max-size 5 --top 20
python timeframe_sweep.py --years 3 --timeframes 1h 2h 4h --scaled-params
python ops_status.py --json
python paper_report.py
python paper_runner.py --once --reset
python paper_runner.py --loop --interval-minutes 60 --tag shadow_2h --timeframe 2h --scale-lookbacks --reset
python paper_report.py --tag shadow_2h
python -m unittest discover -s tests -v
```

For the live/testnet bot, place your API keys in `.env` or environment variables. **Do not switch off `config.TESTNET = True` without going through the gating criteria.**

## Python Version

Python 3.10+ is required (the codebase uses PEP 604 union types such as `pd.DataFrame | None`).

## Safety Notice

This repository is **not** investment advice. Futures trading carries leverage, liquidation, funding, slippage, and API/connectivity risks. Before any live trading, the following stages are mandatory: testnet, paper trading, alarm/monitoring, and a small-capital ramp-up.
