# Binance Futures Trading Bot

A 4-hour Donchian breakout trend-following bot for Binance Futures.

> **Status:** Research and testing phase. The backtest infrastructure has matured, but the bot is **not** ready for live trading. Start with [docs/MULTI_SYMBOL.md](docs/MULTI_SYMBOL.md) and [docs/WALK_FORWARD.md](docs/WALK_FORWARD.md) for the latest decision context.

## Quick Overview

| Item | Value |
|---|---|
| Target capital | 1,000 USDT |
| Primary timeframe | 4 hours |
| Higher timeframe filter | 1D EMA50 |
| Leverage | 3x |
| Risk per trade | 2% |
| Primary signal | Donchian breakout |
| Filters | Volume, ADX, RSI, 1D trend |
| Exits | ATR initial SL, trailing SL, Donchian exit |

## Strategy

**Entry logic:**

1. The 4H close breaks the prior Donchian channel.
2. The bar volume is above a multiple of the 20-bar moving average.
3. ADX is above the trend-strength threshold.
4. RSI is not in extreme overbought/oversold territory.
5. The 1D trend filter confirms the same direction.

**Exit logic:**

- Initial stop-loss: ATR-based.
- Trailing stop: locks in a portion of the gains.
- Early exit: a shorter Donchian channel breaks in the opposite direction.

## Current Findings

- The single-BTC backtest is weak and walk-forward is borderline negative.
- Multi-symbol testing on ETH, SOL, and BNB looks better than BTC.
- 4-symbol walk-forward summary: 3/4 symbols have a positive test average, but the train-vs-test gap is still large.
- Verdict: the strategy may be promising, but overfitting risk remains. Additional robustness testing is required before any testnet/paper-trading stage.

## Files

```text
config.py                    Parameters
data.py                      Live data and exchange queries
indicators.py                ATR, RSI, ADX, Donchian, daily trend
strategy.py                  Signal and exit rules
risk.py                      Position size and SL/TP calculation
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
```

For the live/testnet bot, place your API keys in `.env` or environment variables. **Do not switch off `config.TESTNET = True` without going through the gating criteria.**

## Python Version

Python 3.10+ is required (the codebase uses PEP 604 union types such as `pd.DataFrame | None`).

## Safety Notice

This repository is **not** investment advice. Futures trading carries leverage, liquidation, funding, slippage, and API/connectivity risks. Before any live trading, the following stages are mandatory: testnet, paper trading, alarm/monitoring, and a small-capital ramp-up.
