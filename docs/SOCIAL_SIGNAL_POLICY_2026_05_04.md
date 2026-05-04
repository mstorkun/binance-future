# Social Signal Policy - 2026-05-04

Status: research-only context layer. This does not enable live execution.

## Direct Answer

Real-time social, Telegram, WhatsApp, X, Reddit, YouTube, TradingView, and news
data would strain the bot if the trading loop tried to fetch, parse, score, and
place orders in the same path.

The safe architecture is asynchronous:

1. Source adapters collect allowed/public or consent-based messages.
2. Messages are normalized into symbol, source, text, timestamp, and metadata.
3. `social_signal_policy.py` scores direction, freshness, credibility,
   confirmation, and manipulation risk.
4. The result is cached per symbol for a short TTL.
5. The trading loop reads only the ready cached score.
6. If the score is stale, missing, or errored, the bot fails closed to `wait`.

Social data is never allowed to open a live trade by itself. It can only become
`observe`, `alert_only`, `paper_long`, `paper_short`, or `block`.

## Source Policy

| Source | Allowed path | Bot role |
|---|---|---|
| Telegram | Bot API, channel/group where bot is invited, or user export | Public/consented context |
| WhatsApp | Business/Cloud API or explicit exported chat files | Consented context only |
| X | Official API | Public/news context |
| Reddit | Official Data API under terms | Crowd context |
| Discord | Bot with required permissions and message-content access | Consented community context |
| YouTube | Official Data API comments/search | Slow sentiment context |
| TradingView | Public scripts/ideas/manual URLs, no private scraping | Technical hypothesis context |
| CoinMarketCap/CoinGecko | Official API/pages | Broad retail attention context |
| Regulators/official news | Official feeds/pages | High-credibility risk/news context |

Private-channel scraping and login automation are out of scope. If the bot gets
private WhatsApp/Telegram text, it should be from explicit exports or official
bot/business integrations.

## Scoring

The module scores:

- symbol extraction from allowlisted futures symbols
- long/short/wait text bias
- technical/news/rumor/scam intent
- platform and source credibility
- freshness decay
- price confirmation
- independent confirmation
- source diversity
- manipulation risk from pump language, copy-paste behavior, concentrated
  platform flow, and late-after-move posts

Strong confirmation can create a paper-only context action. Manipulation risk
creates `block`, which should prevent new entries for that symbol until the
cache clears.

## Bot Rule

Social/news context may support a trade only when price action, liquidity,
multi-timeframe candle context, and risk limits already agree. It cannot
override:

- kill switch
- live block
- liquidation guard
- urgent exit cap
- stale data guard
- max drawdown/risk limits

## Sources

- Telegram Bot API: https://core.telegram.org/bots/api
- Telegram data export: https://telegram.org/blog/export-and-more
- WhatsApp Terms: https://www.whatsapp.com/legal/terms-of-service
- WhatsApp Business Platform docs: https://developers.facebook.com/docs/whatsapp
- X API recent search: https://docs.x.com/x-api/posts/search-recent-posts
- Reddit Data API terms: https://redditinc.com/policies/data-api-terms
- Discord message content intent: https://discord.com/developers/docs/events/gateway#message-content-intent
- YouTube Data API quota: https://developers.google.com/youtube/v3/getting-started#quota
- TradingView repainting: https://www.tradingview.com/pine-script-docs/concepts/repainting/
- CFTC virtual currency pump warning: https://www.cftc.gov/LearnAndProtect/AdvisoriesAndArticles/customeradvisory_pumpdump0218.html
- FINRA pump-and-dump warning: https://www.finra.org/investors/insights/pump-and-dump-scams
- SEC social media fraud warning: https://www.sec.gov/oiea/investor-alerts-and-bulletins/socialmediaandfraud
