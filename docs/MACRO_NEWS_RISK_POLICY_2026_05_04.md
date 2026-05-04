# Macro and News Risk Policy - 2026-05-04

## Objective

The bot can decide not to trade. A strong candle/indicator/model signal is not
enough during macro shocks, exchange incidents, thin weekend books, or major
funding/liquidation stress. This layer is a permission gate: it can reduce risk,
block new entries, flatten, or observe only.

This document is research/paper policy. It does not enable live trading.

## Official Calendar Sources

- Federal Reserve FOMC calendar:
  https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- Federal Reserve speeches/testimony:
  https://www.federalreserve.gov/newsevents/speeches-testimony.htm
- BLS release calendar:
  https://www.bls.gov/schedule/news_release/bls.ics
- BLS CPI:
  https://www.bls.gov/schedule/news_release/cpi.htm
- BLS Employment Situation:
  https://www.bls.gov/schedule/news_release/empsit.htm
- BLS PPI:
  https://www.bls.gov/schedule/news_release/ppi.htm
- BEA schedule:
  https://www.bea.gov/news/schedule
- CME FedWatch:
  https://www.cmegroup.com/fedwatch
- Binance announcements:
  https://www.binance.com/en/support/announcement
- Binance Futures liquidation stream:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams
- Binance order book:
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book

## Core Modes

| Mode | Bot behavior |
|---|---|
| `normal` | Strategy active. Dynamic risk model decides size. |
| `reduce_risk` | New trades allowed only with reduced size and stronger confirmation. |
| `block_new_entries` | Existing positions are managed; no fresh entries. |
| `flatten` | Reduce or close exposure before/after severe events. |
| `observe_only` | No new entries. No averaging. Market orders only for emergency exits. |

## Scheduled Macro Rules

All event times are stored in UTC. U.S. sources publish in Eastern Time, so the
calendar loader must convert with daylight saving time.

| Event class | Source | Default window | Bot action |
|---|---|---:|---|
| FOMC decision + press conference | Fed | `T-60m` through at least `T+90m` after presser start | `observe_only`; flatten or max 25% risk by `T-15m` |
| FOMC minutes | Fed | `T-30m` to `T+30m` | `block_new_entries`; reduce open high leverage |
| CPI | BLS | `T-45m` to `T+45m` minimum | `observe_only`; flatten high leverage by `T-10m` |
| Employment Situation / NFP | BLS | `T-45m` to `T+45m` minimum | `observe_only`; extend if headline/unemployment conflict |
| PCE / Personal Income and Outlays | BEA | `T-30m` to `T+30m` | `observe_only`; extend on large core PCE surprise |
| PPI | BLS | `T-30m` to `T+20m` | `block_new_entries`; flatten only if high leverage |
| GDP | BEA | `T-20m` to `T+20m` | `reduce_risk`; use PCE rule if same timestamp |
| Jobless claims | DOL/BLS calendar context | `T-10m` to `T+10m` | `block_new_entries` in stress regimes, otherwise reduce |
| Fed Chair policy speech/testimony | Fed | `T-30m` to `T+45m/+60m` | `block_new_entries` or `observe_only` if policy-focused |
| Treasury refunding / long-end auctions | Treasury | `T-10m` to `T+60m` by event | `reduce_risk` or `block_new_entries` if yields move sharply |

If two Tier 1 events occur on the same day, use the stricter window and stay in
`observe_only` until both post-event windows finish and market stress normalizes.

## Crypto-Specific Rules

| Event | Bot action |
|---|---|
| Binance maintenance/system upgrade | `observe_only` before and after the maintenance window |
| Binance listing/new contract | Symbol-level `observe_only` at launch unless strategy is listing-tested |
| Binance delisting/trading removal | Symbol-level `observe_only`; no new entries |
| Exchange outage/API stale/depth sequence gap | `observe_only` |
| Stablecoin depeg | Market-wide `observe_only`; no new leveraged entries |
| Hack/exploit/security incident | `observe_only` for affected symbol/ecosystem; market-wide if contagion |
| Extreme liquidation burst + funding/OI stress | `flatten` or `observe_only` |

## Weekend and Session Rules

| Window | Bot action |
|---|---|
| Late Friday into weekend | reduce size, avoid fresh swing entries, no market orders except protection |
| Saturday/Sunday thin liquidity | 50-70% lower max size; passive entries preferred |
| Sunday CME reopen / Asia Monday transition | observe first 30 minutes; trade only after spread/depth normalize |
| Funding timestamps `00:00/08:00/16:00 UTC` | no new marginal entries around funding; extend window when funding is extreme |
| U.S. macro windows `08:30 ET`, `10:00 ET`, `14:00 ET` | macro gate overrides all technical signals |

## Scoring Model

Use a `macro_risk_score` from `0` to `100`, but final action is the strictest
result from calendar, surprise, and market-stress gates.

| Score | Mode |
|---:|---|
| `0-24` | `normal` |
| `25-44` | `reduce_risk` |
| `45-64` | `block_new_entries` |
| `65-84` | `flatten` |
| `85-100` | `observe_only` |

Inputs:

- event severity
- time-to-event
- actual-vs-consensus surprise when available
- realized volatility spike
- spread/depth deterioration
- BTC/ETH beta shock
- funding, OI, and liquidation stress
- data/feed quality

Hard overrides:

- Tier 1 event inside `T-5m` to `T+5m`: at least `block_new_entries`
- Tier 1 event plus spread/depth deterioration or volatility spike: `flatten`
- stale/missing market data during event window: `observe_only`
- liquidation burst plus funding extreme plus OI shock: `flatten` or `observe_only`

## Code Hook

`macro_event_policy.py` converts known events into `event_calendar.csv` rows.
`calendar_risk.py` already reads that CSV and `risk.entry_risk_decision()`
blocks or reduces new entries. The next implementation step is an automated
calendar refresher that writes official FOMC/BLS/BEA/Binance events into that
CSV before each trading day.
