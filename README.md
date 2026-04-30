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
| Mature-bot add-ons | Protection layer, exit ladder, bias audit are present but passive by default |

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

- The current candidate is the SOL/ETH/BNB `growth_70_compound` portfolio profile.
- Latest corrected 3-year portfolio backtest: about `+79.54% CAGR` with `7.67%` peak drawdown.
- Portfolio walk-forward: fixed growth profile is positive in `7/7` test periods.
- Monte Carlo remains the live gate: bootstrap/block paths still show meaningful drawdown risk even when ending-equity loss probability is zero in this trade set.
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
bias_audit.py                Lookahead/recursive indicator stability audit
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
python bias_audit.py --symbol SOL/USDT --years 1 --sample-step 96
python paper_runner.py --once --reset
python -m unittest discover -s tests -v
```

For the live/testnet bot, place your API keys in `.env` or environment variables. **Do not switch off `config.TESTNET = True` without going through the gating criteria.**

## Python Version

Python 3.10+ is required (the codebase uses PEP 604 union types such as `pd.DataFrame | None`).

## Safety Notice

This repository is **not** investment advice. Futures trading carries leverage, liquidation, funding, slippage, and API/connectivity risks. Before any live trading, the following stages are mandatory: testnet, paper trading, alarm/monitoring, and a small-capital ramp-up.
