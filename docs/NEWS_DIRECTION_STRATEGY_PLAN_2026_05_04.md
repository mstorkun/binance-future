# News Direction Strategy Plan - 2026-05-04

## Objective

The bot should not blindly trade headlines. It should use trusted news and
official data to decide whether to wait, reduce risk, or allow a directional
long/short only after market reaction confirms the news interpretation.

This layer is research-only until validated with event studies and walk-forward
tests. It does not enable live trading.

## Core Principle

News creates a bias, not a trade.

Directional futures trades require three layers:

1. **Trusted source:** official source or high-reliability Tier 1 source.
2. **Content bias:** bullish, bearish, mixed, or uncertain interpretation.
3. **Market confirmation:** BTC/ETH, volume, volatility, liquidity, and for macro
   news cross-market assets must confirm the same direction.

If any layer is weak, the decision is `wait` or `observe_only`.

## Source Hierarchy

| Tier | Sources | Bot permission |
|---|---|---|
| Official | Fed, BLS, BEA, SEC, CFTC, Treasury, Binance announcements/API/status, project official blogs | Can create risk gate and content bias |
| Tier 1 | Reuters, AP, Bloomberg, WSJ, FT, CNBC, CoinDesk | Can create temporary observe/reduce state; direction needs confirmation |
| Vendor/data | CME FedWatch, ETF flow vendors, Coinglass/Coinalyze, Messari, CoinMarketCal | Context/confirmation; not enough alone for high leverage |
| Social/rumor | X/Telegram/unknown sites | Observe only at most; never direct long/short |

## Macro Direction Logic

| Event | Initial bearish BTC bias | Initial bullish BTC bias | Confirmation required |
|---|---|---|---|
| FOMC | higher rate, fewer cuts, hawkish dots, Powell pushes back on easing | more cuts, lower rate, dovish statement, inflation confidence | yields/DXY/Nasdaq/BTC reaction |
| CPI/PCE/PPI | inflation hotter than forecast | inflation cooler than forecast | 2Y yield, DXY, Nasdaq, BTC event range |
| NFP/jobs | strong payrolls + hot wages + lower unemployment if yields rise | weak labor + cooling wages if Nasdaq/BTC treat it as dovish | yields first, then risk assets |
| GDP | strong growth + hot price index if Fed-hawkish | soft landing interpretation | market reaction decides |
| Fed speeches | higher-for-longer / inflation risk | cuts possible / labor risk | wait for reaction; no text-only trade |

Confirmation matrix:

| Bias | Cross-market reaction | BTC reaction | Decision |
|---|---|---|---|
| Hawkish/risk-off | yields up, DXY up, Nasdaq down | BTC loses event low/support | `short_allowed` |
| Dovish/risk-on | yields down, DXY down, Nasdaq up | BTC reclaims/breaks event high | `long_allowed` |
| Mixed/conflicting | choppy or split | wick/whipsaw only | `wait` |
| Any high-impact event before release | unknown | unknown | `observe_only` |

## Crypto-Specific Direction Logic

| News | Scope | Direction rule |
|---|---|---|
| Binance new listing/perp launch | symbol | wait first 15-30m; direction only after spread/depth/funding stabilize |
| Binance delisting | symbol | close-only / no new entries; ignore dip-buy signals |
| Binance outage/API degradation | market | observe-only; no direction |
| Stablecoin depeg | market/collateral | risk-off; reduce USDT-margined exposure |
| ETF approval/regulatory clarity | BTC/ETH/high beta | bullish only if spot/perp volume and OI confirm |
| ETF outflow/regulatory enforcement | BTC/ETH/affected assets | bearish only if price confirms and liquidity is normal |
| Token unlock | symbol | bearish pressure candidate; no short unless price/OI/CVD confirm |
| Hack/exploit | affected symbol/ecosystem | bearish/close-only until official recovery clarity |
| Liquidation cascade | market/symbol | continuation or reversal only after OI, funding, CVD, and price structure confirm |

## Implementation Shape

`macro_event_policy.py` handles scheduled risk windows and writes
`event_calendar.csv` compatible rows.

`news_direction_policy.py` handles source reliability, content bias, and market
confirmation:

- unconfirmed source => `observe_only`, never directional
- official/Tier 1 source + uncertain content => `observe_only`
- clear content + weak market reaction => `observe_only`
- clear content + opposite market reaction => `block_new_entries`
- clear content + aligned market reaction => `directional_allowed`

The strategy engine should consume this as a permission layer:

- `trade_bias=long`: only long signals may pass, size still dynamic
- `trade_bias=short`: only short signals may pass, size still dynamic
- `trade_bias=wait`: no new technical entries

## Validation Gates

Do not promote the news direction layer until it passes:

- event-study backtests around official timestamps
- separate pre-event observe vs post-confirmation directional variants
- actual-vs-forecast surprise tests for CPI/NFP/PCE/FOMC
- latency assumptions for news/source availability
- spread/slippage stress in event windows
- out-of-sample folds by year and event type
- false headline/rumor rejection tests
- no live use while audit P0 blockers remain open

## Source Pointers

- Fed FOMC: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- Fed speeches/testimony: https://www.federalreserve.gov/newsevents/speeches-testimony.htm
- BLS CPI: https://www.bls.gov/news.release/cpi.nr0.htm
- BLS Employment Situation: https://www.bls.gov/news.release/empsit.nr0.htm
- BLS PPI: https://www.bls.gov/ppi/news-release/home.htm
- BEA PCE: https://www.bea.gov/data/personal-consumption-expenditures-price-index
- BEA GDP: https://www.bea.gov/data/gdp/gross-domestic-product
- Treasury yields: https://home.treasury.gov/resource-center/data-chart-center/interest-rates
- ICE DXY: https://www.ice.com/market-data/indices/currency-indices
- CME FedWatch: https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html
- Binance announcements: https://www.binance.com/en/support/announcement
- Binance exchange info: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information
- Binance liquidation stream: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/All-Market-Liquidation-Order-Streams
