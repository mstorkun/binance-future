# Binance Bot Handoff - 2026-05-05

This file is the restart anchor. If VS Code or Codex is reopened, read this
file first, then `AI_MEMORY.md`, then verify current state with git and the
preflight commands below.

## Current Repo State

- Repo: `C:\Users\mustafa devecioglu\Documents\GitHub\binance-bot`
- Remote: `https://github.com/mstorkun/binance-future.git`
- Branch: `main`
- Latest pushed research commit before this handoff: `8ee71a9 Add volatility breakout regime V2`
- This handoff commit should save the remaining tracked walk-forward artifact
  plus this restart note.

## Latest Strategy Work

- HTF support/resistance reversion was added as research-only and failed strict
  promotion: severe total return `-2.0765%`, CAGR `-1.2687%`, max DD
  `11.4489%`, `5/12` positive folds, sample `31`.
- Volatility Breakout V1 was added as research-only and failed strict
  promotion: severe total return `-73.2745%`, CAGR `-55.1919%`, max DD
  `75.2624%`, `1/12` positive folds, sample `296`.
- Volatility Breakout V2 added BTC regime-permission gates: BTC 72h
  volatility, BTC 4h ADX, BTC shock, and BTC absolute funding. It improved the
  loss profile but still failed strict promotion: severe total return
  `-28.2179%`, CAGR `-18.2658%`, max DD `35.0186%`, PBO `0.5`, DSR proxy
  `-5.0906`, Sortino `-0.3894`, `4/12` positive folds, sample `107`.

## Important Safety State

- Live trading must remain blocked unless `go_live_preflight.py` is green and
  there is explicit approval.
- Last verified preflight after V2: `go_live_blocked`, exit `2`.
- Do not enable `LIVE_TRADING_APPROVED`, disable `TESTNET`, or connect a
  research candidate into paper/live behavior just because it improved a
  report. Promotion requires strict evidence first.

## Restart Verification Commands

Run these after reopening:

```powershell
git status --short
git log -3 --oneline
python go_live_preflight.py
python -m pytest tests/test_volatility_breakout.py tests/test_htf_reversion.py tests/test_hurst_mtf_momentum.py tests/test_safety.py -q
```

Expected after this handoff is committed and pushed:

- `git status --short` should be clean.
- The preflight should still block live trading unless the user explicitly
  changes live credentials/profile settings.
- The focused test set should remain green.

## Next Useful Research Step

Do not spend the next step on live execution gates. The last useful learning is
that regime filters reduce damage but do not create enough edge. A sensible
next experiment is a different family, for example:

- real liquidation feed experiment if paid/real data is available;
- BTC-dominance / rotation research;
- strict mean-reversion variant with enough sample size;
- volatility expansion with a different exit model, still research-only.
