# System Architecture

## Component Diagram

```
                     ┌─────────────────┐
                     │     bot.py      │  Main loop (live execution)
                     │  schedule.run() │
                     └────────┬────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐         ┌─────────────┐       ┌────────────┐
   │ data.py │         │ strategy.py │       │   risk.py  │
   │ (ccxt)  │         │ get_signal  │       │ pos_size   │
   └────┬────┘         │ check_exit  │       │ sl_tp      │
        │              │ trail_stop  │       │ daily_lim  │
        │              └──────┬──────┘       └──────┬─────┘
        │                     │                     │
        │                     ▼                     │
        │              ┌──────────────┐             │
        │              │indicators.py │             │
        │              │ EMA  Wilder  │             │
        │              │ ADX  RSI ATR │             │
        │              └──────────────┘             │
        │                                           │
        ▼                                           ▼
   ┌──────────────┐                          ┌─────────────────┐
   │ Binance API  │  ◄────────────────────── │ order_manager.py│
   │              │      market/stop order    │ open_position  │
   │              │                           │ update_trail   │
   │              │                           │ close_market   │
   └──────────────┘                           └─────────────────┘
```

## Data Flow (Live Bot)

```
Once per hour (to catch the 4H candle close):

1. data.fetch_balance()        → balance
2. data.fetch_ohlcv()          → last 200 candles
3. indicators.add_indicators() → add EMA, ADX, RSI, ATR
4. _has_open_position()        → query open position from exchange

5a. POSITION OPEN:
    - strategy.check_exit() → has the trend reversed?
        → Yes → close_position_market() + clear state
        → No  → update trailing SL
            (extreme = update max/min)
            (if new SL is better than old → cancel + new stop_market)

5b. NO OPEN POSITION:
    - strategy.get_signal() → LONG/SHORT/None
        → None → exit
        → Signal → om.set_leverage() → om.open_position()
            (atomic: market + stop_market, on failure → rollback)
            (save active_position state)

6. risk.daily_loss_exceeded() → daily limit exceeded?
    → Yes → close_all() and stop
```

## Data Flow (Backtest)

```
1. fetch_long_history(years=3)  → 3 years of 4H data (6570 bars)
2. indicators.add_indicators() → add indicators
3. for each bar:
    - get_signal(window) → is there a signal?
    - If yes: simulate entry at next bar's open
    - On subsequent bars:
        - trend reversal → close
        - trailing SL hit → close
    - Compute PnL, deduct commission + slippage
4. Write to CSV, summary report
```

## Data Flow (Walk-Forward)

```
1. Pull 6570 bars of data
2. for period in 3:
    - train_window = bar[start : start + 3000]
    - test_window  = bar[start + 3000 : start + 4000]
    - find_best_params(train_window) → test 54 combinations
    - run_segment(test_window, best_params) → out-of-sample
    - save result
    - start += 1000
3. Compare train average vs test average
```

## State Management

**Bot state (`bot.py`):**
- `active_position`: dict | None
  - `side`: "long" / "short"
  - `entry`: float
  - `sl`: float (changes as trailing updates)
  - `size`: float (contracts)
  - `extreme`: float (max for long, min for short)
- `daily_start_bal`: float | None (resets at UTC 00:01)

**Exchange state:**
- `exchange.fetch_positions(SYMBOL)` — source of truth
- The bot queries exchange state every cycle and synchronizes its own state to it (drift prevention)

## Critical Design Decisions

### 1. Trailing SL — Manual on the Bot Side

**Alternative:** Binance's `TRAILING_STOP_MARKET` order type.

**Chosen:** Bot cancels old SL and places new one each cycle.

**Reason:** Binance's trailing order is based on callback rate (percentage). Our rule "give back 15% of profit" is dynamic (recomputed each bar). Manual control is more flexible.

**Risk:** If the exchange price moves between cancel + create, the position is left unprotected. ~50ms window. Low risk.

### 2. Atomic Position Open + Rollback

**Alternative:** Sequential order → SL → trailing.

**Chosen:** Market order, then SL; on failure, market close.

**Reason:** During crypto volatility spikes the SL order can be rejected. The position must not be left unprotected.

### 3. Wilder Smoothing

**Alternative:** EMA span (easy).

**Chosen:** Wilder (`alpha=1/N`).

**Reason:** Standard RSI/ADX/ATR use Wilder. Using span made indicators incompatible with TradingView and Binance.

## Test Strategy

| Test Type | Method | Goal |
|---|---|---|
| Historical backtest | `backtest.py` | Does the strategy work? |
| Parameter sweep | `optimize.py` | Best parameters? |
| Walk-forward | `walk_forward.py` | Is there overfitting? |
| Testnet (Binance) | `bot.py` + testnet | Does live order logic work? |
| Live (small capital) | `bot.py` + live | What is real slippage/funding? |

## Dependencies

```
ccxt>=4.2.0       # Binance API
pandas>=2.0.0     # Data/indicators
schedule>=1.2.0   # Scheduler
python-dotenv     # .env loading
```

`pandas-ta` and `numba` are not used — plain pandas is sufficient and easy to install.
