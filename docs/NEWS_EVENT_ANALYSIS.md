# News and Event Risk Analysis

Scope: last 12 months from 2025-04-30 to 2026-04-30. This file is for
teaching the bot how to convert market-moving news into risk controls. It is
not a claim that news headlines alone can predict direction.

## What moved crypto sharply

### 1. Tariff / geopolitical / macro risk-off shocks

Observed pattern:
- Surprise tariff or geopolitical headlines can hit crypto while traditional
  markets are closed.
- The largest damage happens when the headline meets high leverage, thin
  weekend liquidity, and crowded positioning.
- Ex-post surprise events must not be inserted into historical backtests as if
  the bot knew them before publication.

Examples:
- 2025-10-10: Trump China tariff threat triggered a record crypto liquidation
  cascade. CoinDesk reported roughly USD 19B liquidations and BTC falling from
  record-high conditions toward the USD 107K-110K zone.
- 2026-02-02: Reuters reported USD 2.56B bitcoin liquidations after a broader
  risk-asset selloff and renewed tariff/Fed-chair concerns.

Bot rule:
- If surprise tariff/geopolitical headline is detected: `pre_minutes=0`,
  `post_minutes=240-1440`, `risk_mult=0.10-0.25`, `block_new_entries=true` for
  the first 1-4 hours if volatility is extreme.
- For backtests, do not use pre-event blocking on surprise headlines. Only test
  post-publication cooldown.

### 2. Fed, CPI, payrolls, PCE and Jackson Hole

Observed pattern:
- Crypto reacts as a high-beta liquidity asset: hawkish Fed / hot inflation /
  stronger jobs usually reduces risk appetite; dovish guidance can trigger
  rebounds.
- The dangerous part is not only the release minute; the first 2-4 hours after
  the release can include whipsaw.

Examples:
- 2025-08-19 to 2025-08-22: markets de-risked into Jackson Hole as rate-cut
  expectations changed, then BTC pushed higher after Powell opened the door to
  a September cut.
- 2025-07-14: BTC was above USD 120K while markets awaited inflation data and
  U.S. crypto legislation.

Bot rule:
- Scheduled high-impact event: `pre_minutes=120-240`, `post_minutes=120-240`,
  `risk_mult=0.25-0.50`.
- If ADX is weak, ATR/close is elevated, or funding/OI is crowded, use
  `block_new_entries=true` during the event window.
- If the event is dovish/bullish after publication, do not auto-long. Allow
  normal strategy signals again only after a cooldown and spread/ATR normalize.

### 3. ETF flows, institutional demand, and crypto legislation

Observed pattern:
- ETF inflows and pro-crypto policy can create persistent upside trend, but
  they also attract crowded leverage near highs.
- Positive ETF/regulatory news is better used as a permission filter, not a
  standalone buy signal.

Examples:
- 2025-07-11: Reuters/Investing reported BTC near USD 119K with strong U.S.
  spot BTC ETF flows and USD 6.3B ETF trading volume.
- 2025-10-05: Reuters reported BTC above USD 125K amid ETF interest and U.S.
  government-shutdown uncertainty.
- 2025-07-14: CNBC linked BTC above USD 120K to ETF inflows and U.S. "Crypto
  Week" legislation.

Bot rule:
- Sustained positive ETF/regulatory regime: no block; cap final risk at
  `1.00-1.25`.
- If price is at fresh ATH and RSI/ATR are hot, do not increase risk. Keep
  normal or reduce to `0.75-0.90`.
- Negative ETF-flow streak or failed legislation headline: `risk_mult=0.50-0.75`
  for 1-3 days, especially for long entries.

### 4. Exchange hacks, outages, delistings, and network incidents

Observed pattern:
- Exchange/security news usually creates asset-specific or venue-specific risk.
- It is often not a market-wide directional signal unless the exchange is large
  or withdrawals/trading are affected.

Examples:
- 2025-05-15: Reuters/AP reported Coinbase customer-data breach and possible
  USD 180M-400M cost; Coinbase stock fell, while broad crypto impact was more
  reputational than a clean BTC signal.
- 2025-05-01: CoinDesk reported MOVE falling after Coinbase suspension news and
  market-maker concerns.

Bot rule:
- If affected symbol is in `SYMBOLS`: block new entries on that symbol for
  12-48 hours.
- If major exchange withdrawals/trading are suspended: market-wide
  `risk_mult=0.25-0.50` until official resolution.
- Listing/delisting announcements are not enough to trade in this bot. Use
  them mainly to avoid unstable liquidity windows.

### 5. Liquidation cascades and thin liquidity

Observed pattern:
- Many sharp candles are not caused by a new fundamental fact alone. They are
  forced-flow events: high open interest, one-sided funding, low order-book
  depth, and stop/liq cascades.
- Weekend and late U.S. session events are especially fragile because liquidity
  can be thinner.

Bot rule:
- Weekend: `risk_mult=0.70`.
- Daily close/open and funding windows: reduce risk, already handled by
  `calendar_risk.py`.
- If later we add open-interest/funding-skew data: block entries when funding
  is extreme and ATR spike confirms liquidation risk.

## Source ranking

Use this order when the bot or operator creates `event_calendar.csv` entries:

1. Primary official sources:
   - Fed FOMC calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
   - BLS CPI / Employment release schedules: https://www.bls.gov/cpi/ and
     https://www.bls.gov/schedule/news_release/empsit.htm
   - BEA release schedule: https://www.bea.gov/news/schedule/
   - Binance announcements: https://www.binance.com/en/support/announcement
   - Exchange official status pages and issuer/ETF official releases
2. Tier-1 reporting:
   - Reuters, AP, CNBC, CoinDesk
3. Aggregators / event calendars:
   - CoinMarketCal API: https://coinmarketcal.com/id/api
   - CoinMarketCap API: https://coinmarketcap.com/api/documentation/
   - CryptoPanic-style news aggregation can be useful, but require source
     confirmation before blocking or increasing risk.

## Production source plan

The bot should learn news from a source pipeline, not from one website:

| Layer | Sources | Bot usage |
|---|---|---|
| Official scheduled macro | Fed, BLS, BEA calendars | Preload event windows into `event_calendar.csv` |
| Official crypto venue/project | Binance announcements, exchange status pages, project blogs/X only when verified | Symbol/venue-specific block or cooldown |
| Tier-1 market news | Reuters, AP, CNBC, CoinDesk | Confirm surprise events and classify market-wide impact |
| Aggregators | CoinMarketCal, CoinMarketCap, CryptoPanic | Early alert only; no trade decision without confirmation |
| Market reaction | Binance OHLCV, volume, funding, later open interest/order-book depth | Confirms whether the market actually cares |

Decision rule:

- One official source is enough for scheduled events and exchange notices.
- Surprise macro/geopolitical events should require either one tier-1 source
  plus strong market reaction, or two reliable sources.
- Social-media-only rumors should never open a position. They may only reduce
  risk temporarily if market reaction is already abnormal.

## Event calendar format

`event_calendar.csv` columns:

```csv
timestamp_utc,event,impact,pre_minutes,post_minutes,risk_mult,block_new_entries
2026-05-06 18:00:00,FOMC rate decision,high,240,240,0.25,true
2026-05-13 12:30:00,US CPI,high,180,240,0.35,true
2026-05-15 00:00:00,major exchange outage,high,0,720,0.25,true
```

Important:
- Scheduled events may use `pre_minutes`.
- Surprise events must use `pre_minutes=0` to avoid lookahead bias.
- `risk_mult` multiplies the market-state multiplier, so multiple active risks
  compound.

## Live news watcher design

Next implementation step, if API keys are available:

1. Poll sources every 60-300 seconds.
2. Normalize to `{timestamp_utc, source, url, title, symbols, category, impact}`.
3. Deduplicate near-identical headlines.
4. Require confirmation:
   - official source for exchange/listing/outage/regulation;
   - two tier-1 sources for geopolitical/macroeconomic surprise headlines;
   - official calendar for scheduled macro.
5. Map category to action:
   - high uncertainty: block or reduce;
   - positive persistent regime: permit normal risk, never blind buy;
   - affected-symbol incident: symbol-specific block;
   - unconfirmed rumor: log only.
6. Write confirmed items to `event_calendar.csv` or an in-memory risk overlay.

## Impact prediction model

The bot should not try to know the future. It should estimate the likely
distribution of outcomes and choose a defensive action. The scoring logic is:

```text
impact_score =
  source_reliability
  x event_type_weight
  x surprise_weight
  x affected_market_weight
  x current_regime_weight
  x first_reaction_confirmation
```

Inputs:

- Source reliability: official source > Reuters/AP/CNBC/CoinDesk >
  aggregator/social.
- Event type: Fed/CPI/tariff/exchange hack/liquidation cascade have higher
  base impact than routine announcements.
- Surprise: scheduled CPI/FOMC has known time but unknown result; surprise
  tariff, hack, outage, delisting has no valid pre-event backtest knowledge.
- Affected market: BTC/ETH or Binance-wide issue is market-wide; MOVE-style
  suspension is symbol-specific.
- Current regime: high ATR, weak order-book depth, extreme funding, high open
  interest and weekend conditions amplify moves.
- First reaction: price/volume/spread/OI response in the first 5-60 minutes
  confirms whether the market cares.

`news_impact.py` implements the first deterministic version of this model. It
maps normalized news to:

- direction: `bullish`, `bearish`, or `uncertain`
- impact: `low`, `medium`, or `high`
- `risk_mult`
- `block_new_entries`
- post-event cooldown window

The output is designed to feed `event_calendar.csv`; it is not a standalone
trading signal.

For directional entries, the bot needs a second layer:

1. Wait for the news to be public.
2. Measure post-news reaction with `measure_market_reaction()`:
   - price change versus the pre-event close
   - volume expansion versus recent average
   - high-low range versus ATR
3. Use `trade_bias_from_news_and_reaction()` only when:
   - the news classification has a clear direction,
   - the actual market reaction confirms the same direction,
   - reaction strength is high enough,
   - the normal strategy is not blocked by calendar/risk controls.

Example:

```text
Reuters tariff shock -> bearish/high
First 60m reaction: -1.8%, 2.7x volume, 1.9 ATR range -> bearish/strong
Bias: short allowed, but only if strategy/market filters also agree.
```

Counterexample:

```text
Good ETF-flow headline -> bullish/medium
First 60m reaction: flat price, weak volume -> no trade.
```

## Sources used for this analysis

- Reuters/Investing, 2026-02-02: https://www.investing.com/news/economy-news/crypto-market-volatility-triggers-25-billion-in-bitcoin-liquidations-4479819
- CoinDesk, 2025-10-15: https://www.coindesk.com/coindesk-indices/2025/10/15/crypto-s-black-friday
- CoinDesk, 2025-10-10: https://www.coindesk.com/markets/2025/10/10/bitcoin-crashes-below-usd110k-cryptos-in-freefall-on-further-trump-tariff-on-china
- Reuters/Investing, 2025-07-11: https://www.investing.com/news/cryptocurrency-news/bitcoin-price-today-hits-new-record-high-above-118k-as-etf-inflows-surge-4131193
- Reuters/Investing, 2025-10-05: https://www.investing.com/news/forex-news/bitcoin-hits-alltime-high-above-125000-4271437
- CoinDesk, 2025-10-02: https://www.coindesk.com/markets/2025/10/02/bitcoin-surges-above-usd119k-as-u-s-government-shutdown-takes-effect-btc-options-look-cheap
- CoinDesk, 2025-08-22: https://www.coindesk.com/markets/2025/08/21/powell-puts-september-rate-cut-in-play-bitcoin-pushes-higher
- CNBC, 2025-07-14: https://www.cnbc.com/2025/07/14/bitcoin-hits-new-all-time-high-above-120000-fueled-by-etf-inflows-crypto.html
- AP, 2025-05-15: https://apnews.com/article/e3ef5297dfea296eb7b7320d8c58647e
- Binance Academy funding rates: https://www.binance.com/en/academy/articles/what-are-funding-rates-in-crypto-markets
