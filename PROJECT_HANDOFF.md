# Binance Bot Handoff - 2026-05-05

This file is the restart anchor. If VS Code or Codex is reopened, read this
file first, then `AI_MEMORY.md`, then verify current state with git and the
preflight commands below.

## Current Repo State

- Repo: `C:\Users\mustafa devecioglu\Documents\GitHub\binance-bot`
- Remote: `https://github.com/mstorkun/binance-future.git`
- Branch: `main`
- Latest pushed research commit before this handoff update: `8d5c0a8 Add market rotation overlay walk-forward`
- Current handoff update: range mean-reversion strict walk-forward diagnostic.

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
- Market rotation context diagnostic was added as report-only:
  `market_rotation_report.py` and
  `docs/MARKET_ROTATION_CONTEXT_2026_05_05.md`. It annotates existing
  `portfolio_trades.csv` entries with prior closed 4h BTC/ETH leadership
  context. Overall stays the same `264` trades / `83.3333%` win rate /
  `10271.77` PnL. Useful signal: `with_rotation` has `159` trades and
  `6756.27` PnL / PF `21.3827`, while `against_rotation` has only `11` trades
  and `-235.06` PnL / PF `0.5522`. This is diagnostic evidence only; the next
  valid step is an entry-time walk-forward rotation overlay, not paper/live
  activation.
- Market rotation overlay walk-forward was added as report-only:
  `market_rotation_overlay.py`,
  `docs/MARKET_ROTATION_OVERLAY_WF_2026_05_05.md`,
  `market_rotation_overlay_report.json`, and
  `market_rotation_overlay_trades.csv`. It trains on earlier annotated trades
  and reduces weak/negative rotation buckets only in the next chronological test
  slice. Real run result: baseline test `120` trades / `6886.98` PnL / PF
  `31.1677`; overlay test identical, `0` reduced trades and `0.0` delta PnL.
  Decision remains `benchmark_only`; rotation diagnostic did not survive
  walk-forward as an actionable overlay.
- Range mean-reversion was added as a separate research-only family:
  `range_reversion_signal.py`, `range_reversion_report.py`,
  `tests/test_range_reversion.py`, and
  `docs/RANGE_REVERSION_REPORT_2026_05_05.md`. It uses prior closed 1h bars,
  4h low-ADX regime context, optional reclaim entries, daily trend opposition
  guard, 96 candidate grid, 12-fold walk-forward, severe cost stress, PBO,
  concentration, tail, and crisis gates. Real result: strict `benchmark_only`;
  severe total return `-51.8707%`, CAGR `-44.7446%`, max DD `52.1327%`,
  `1/12` positive folds, PBO `0.0`, DSR proxy negative, sample `136` trades.
  This family is not ready for paper/live and should not be enlarged with more
  filters without a new independent reason.

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
python -m pytest tests/test_range_reversion.py tests/test_volatility_breakout.py tests/test_htf_reversion.py tests/test_hurst_mtf_momentum.py tests/test_safety.py -q
```

Expected after this handoff is committed and pushed:

- `git status --short` should be clean.
- The preflight should still block live trading unless the user explicitly
  changes live credentials/profile settings.
- The focused test set should remain green.

## Next Useful Research Step

Do not spend the next step on live execution gates. The last useful learning is
that Hurst-MTF, HTF support/reversion, volatility breakout, rotation overlay,
and simple range mean-reversion all failed strict promotion. A sensible next
experiment should use genuinely different evidence, for example:

- real liquidation feed experiment if paid/real data is available;
- BTC dominance / external market breadth if real historical data is available;
- news/event-reaction dataset research;
- another external-data stat-arb lead, still research-only.
