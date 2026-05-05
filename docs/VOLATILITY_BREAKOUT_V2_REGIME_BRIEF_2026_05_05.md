# Volatility Breakout V2 Regime Gate Brief - 2026-05-05

Status: research-only candidate. This does not enable paper, testnet, or live execution.

## Why This Variant Exists

The user asked whether the bot can avoid a fixed `4h only` mindset and decide
when to trade or wait. The answer is yes, but only as a tested regime layer.

V1 produced enough trades but failed strict gates:

- Severe total return `-73.2745%`.
- CAGR `-55.1919%`.
- Max DD `75.2624%`.
- Positive folds `1/12`.
- Sample `296` trades.

The diagnostic did not justify a live/paper rule, but it suggested that BTC
regime quality may matter. V2 therefore keeps the V1 breakout signal and adds
explicit BTC regime-permission gates.

## Rule Family

Keep V1:

- 1h Bollinger-bandwidth squeeze.
- 1h volume-confirmed range breakout.
- 4h trend/ADX alignment.
- BTC market-leader direction gate.
- Vol-targeted sizing, 10x leverage cap, max 20% equity margin per position.

Add V2 permission gates:

- BTC 72h realized volatility must be below a tested max.
- BTC 4h ADX must be below a tested max.
- BTC absolute shock z-score must be below a tested max.
- BTC absolute funding rate must be below a tested max.

If the V1 signal fires but a V2 regime gate fails, the bot stays flat.

## Candidate Grid

V2 deliberately narrows the V1 base grid to avoid uncontrolled curve-fitting:

- Breakout lookback: `72`.
- Squeeze lookback: `120`, `240`.
- Squeeze percentile max: `0.15`, `0.25`.
- Volume z min: `1.2`, `1.8`.
- 4h ADX min: `15`, `20`.
- Target vol: `0.45`.
- BTC 72h vol max: `0.45`, `0.55`.
- BTC 4h ADX max: `26`, `30`.
- BTC shock max: `3`, `4`.
- BTC funding abs max: `0.00012`, `0.00020`.

Total strict V2 grid: `256` candidates.

## Strict Gate

Same gate as prior candidates:

- Net CAGR after severe cost stress `>=80%`.
- PBO `<0.3`.
- Walk-forward positive folds `>=7/12`.
- DSR proxy `>=0`.
- Sortino `>=2.0`.
- No symbol over `40%` of positive PnL.
- No month over `25%` of positive PnL.
- Tail capture `50-80%`.
- Crisis alpha positive on `2024-08-05` and `2025-10-10`.
- Sample `>=200` trades.

## Decision Rule

If V2 fails, it stays `benchmark_only`. Do not connect it to paper/live behavior
unless every strict gate passes first.
