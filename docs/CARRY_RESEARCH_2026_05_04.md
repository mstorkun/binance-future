# Funding Carry Research - 2026-05-04

This note records the first broad Binance funding-rate carry scan after the
post-audit strategy pivot discussion. It is research-only and does not approve a
live delta-neutral executor.

## Method

Command:

```bash
python carry_research.py --auto-universe --days 180 --min-quote-volume-usdt 50000000 --max-symbols 80 --out carry_candidates.csv --universe-out carry_universe.csv --json
```

Universe filters:

- Binance USDT-settled linear perpetual.
- Active matching Binance spot pair, required for spot-long/perp-short carry.
- ASCII alphanumeric base asset only, to avoid operationally fragile listings.
- Minimum 24h futures quote volume: `50,000,000` USDT.
- Auto-universe minimum samples: `days * 2`, so the 180-day scan requires at
  least `360` funding observations.

Cost and benchmark assumptions:

- Four taker legs: spot buy, perp short, spot sell, perp cover.
- Entry/exit cost proxy: `0.46%`.
- Opportunity benchmark: `6%` APR USDT Earn-style hurdle.
- Pass condition: positive net APR after costs vs benchmark and positive
  funding ratio at least `55%`.

## Result

- Universe size: `32` symbols.
- Passing candidates: `0`.
- Best ASCII/liquid candidate: `TST/USDT:USDT`.
- Best annualized net after entry/exit cost: `3.7441%`.
- Best net APR after the `6%` benchmark: `-2.2559%`.

Top rows:

| Symbol | Samples | Positive funding | Gross funding APR | Net annualized after cost | Net vs 6% benchmark | Max DD |
|---|---:|---:|---:|---:|---:|---:|
| TST/USDT:USDT | 1080 | 94.9074% | 4.2105% | 3.7441% | -2.2559% | 0.4453% |
| LINK/USDT:USDT | 540 | 73.3333% | 3.8536% | 2.9209% | -3.0791% | 0.0436% |
| MEGA/USDT:USDT | 564 | 97.3404% | 3.1402% | 2.2471% | -3.7529% | 1.0617% |
| UNI/USDT:USDT | 540 | 71.1111% | 3.0697% | 2.1368% | -3.8632% | 0.1406% |
| NEAR/USDT:USDT | 540 | 69.0741% | 2.4120% | 1.4792% | -4.5208% | 0.2644% |

## Decision

The broad scan does not support building a live carry executor yet. The carry
research lane remains open, but the next step should be a deeper historical
study with:

- Longer history per symbol where available.
- Dynamic entry/exit thresholds instead of always-on carry.
- Funding spike and borrow/transfer/liquidity stress.
- Portfolio allocation across only periods where carry exceeds the benchmark
  by a real margin.

Current action: keep Donchian paper tests running as benchmark, keep live
blocked, and do not allocate engineering time to live spot/perp execution until
carry shows stronger historical edge.

## Dynamic Threshold Follow-up

The next pass tested whether selective entry/exit thresholds improve the
always-on carry result. The signal uses only prior funding observations, so the
current funding payment is not used to decide whether that same payment is
collected.

Command:

```bash
python carry_research.py --auto-universe --days 180 --min-quote-volume-usdt 50000000 --max-symbols 80 --dynamic-enter-grid 0.00005 0.000075 0.0001 0.00015 --dynamic-exit-grid 0 0.00002 0.00005 --dynamic-signal-window 3 --out carry_candidates.csv --universe-out carry_universe.csv --json
```

Result:

- Latest dynamic scan size: `33` spot-backed liquid USDT perpetuals.
- Static carry pass count: `0`.
- Single dynamic-threshold pass count: `0`.
- Best grid-optimized dynamic-threshold pass count: `0`.
- Best active grid candidate: `PARTI/USDT:USDT`.
- Best active grid settings: enter `0.000075`, exit `0.00005`.
- Best active grid result: `-0.3764%` net after entry/exit costs and
  `-0.4477%` versus the prorated `6%` USDT benchmark.
- Reason it still fails: only `13` active funding periods, below the minimum
  active-history threshold.

Top active dynamic rows:

| Symbol | Entries | Active periods | Enter | Exit | Net after cost | Net vs benchmark | Reason |
|---|---:|---:|---:|---:|---:|---:|---|
| PARTI/USDT:USDT | 1 | 13 | 0.000075 | 0.00005 | -0.3764% | -0.4477% | insufficient_active_periods |
| BTC/USDT:USDT | 1 | 53 | 0.0001 | 0.00002 | -0.1605% | -0.4509% | insufficient_active_periods |
| BNB/USDT:USDT | 1 | 6 | 0.0001 | 0.00002 | -0.4274% | -0.4603% | insufficient_active_periods |
| XRP/USDT:USDT | 1 | 4 | 0.0001 | 0.00005 | -0.4452% | -0.4672% | insufficient_active_periods |
| MEGA/USDT:USDT | 1 | 3 | 0.000075 | 0 | -0.4781% | -0.4945% | insufficient_active_periods |

Conclusion: simple Binance spot/perp carry still has no executor-worthy edge
under the current fee, cost, and USDT benchmark assumptions. The next research
branch should be predictive funding models, cross-exchange basis/funding, or a
separate stat-arb overlay; not live spot/perp execution.
