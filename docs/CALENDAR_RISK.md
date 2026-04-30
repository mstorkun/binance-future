# Calendar Risk Controls

`calendar_risk.py` adds a final risk gate before new entries. It does not
predict the news result. It only reduces or blocks entries during windows where
spread, slippage, liquidation cascades, and fake breakouts are more likely.

## Built-in rules

Configured in `config.py`:

- Weekend: `WEEKEND_RISK_MULT = 0.70`
- Weekly open: `WEEKLY_OPEN_RISK_MULT = 0.75`
- Funding window near 00:00, 08:00, 16:00 UTC:
  `FUNDING_RISK_MULT = 0.90`
- Daily close/open near 00:00 UTC: `DAILY_CLOSE_RISK_MULT = 0.85`
- Final risk clamp: `FINAL_RISK_MIN_MULT = 0.10`,
  `FINAL_RISK_MAX_MULT = 1.25`

These values are intentionally defensive. The bot should survive uncertainty
first, then only increase size modestly when technical and event context agree.

## Manual event file

`event_calendar.csv` is read on each risk decision. Columns:

```csv
timestamp_utc,event,impact,pre_minutes,post_minutes,risk_mult,block_new_entries
```

Example rows:

```csv
2026-05-06 18:00:00,FOMC rate decision,high,240,240,0.25,true
2026-05-13 12:30:00,US CPI,high,180,240,0.35,true
2026-05-15 00:00:00,major exchange outage,high,0,720,0.25,true
```

Rules:

- Scheduled events may use `pre_minutes`.
- Surprise headlines must use `pre_minutes=0`; otherwise historical backtests
  get lookahead bias.
- `block_new_entries=true` blocks only new entries. It does not close existing
  positions.
- `risk_mult` compounds with market-state risk. Example: market `0.65` and
  calendar `0.35` gives final `0.2275`, then clamps to the configured minimum.

## Suggested event defaults

| Event type | pre | post | risk_mult | block |
|---|---:|---:|---:|---|
| FOMC decision / Powell presser | 240m | 240m | 0.25 | true |
| CPI / NFP / PCE | 180m | 240m | 0.35 | true if ATR high |
| Jackson Hole / major Fed speech | 180m | 240m | 0.35 | true if volatility high |
| Surprise tariff/geopolitical headline | 0m | 240-1440m | 0.10-0.25 | true |
| Major exchange outage/hack | 0m | 720-2880m | 0.25-0.50 | true |
| ETF flow/regulatory positive trend | 0m | 1440m | 1.00-1.25 | false |
| Unconfirmed rumor | 0m | 0m | 1.00 | false, log only |

## Implementation path

Current state:

- Live bot calls `risk.entry_risk_decision()` before opening a position.
- Portfolio backtest uses the same entry risk gate.
- `event_calendar.csv` is header-only by default to avoid accidental historical
  lookahead.

Next step:

- Add a `news_watcher.py` module after choosing data providers/API keys.
- The watcher should confirm sources and write only confirmed, timestamped
  events into `event_calendar.csv` or an in-memory risk overlay.
