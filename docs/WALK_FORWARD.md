# Walk-Forward Analysis

Goal: Measure whether parameters are overfitting to historical data.

Method:

- Train: 3000 4H bars, approximately 16-18 months.
- Test: 500 4H bars, approximately 3 months.
- Roll: 500 4H bars.
- In each period, parameters are selected only on the train set, then tested in the test period.

## Current BTC Result

`walk_forward_results.csv` contains 7 test windows from the latest run.

| Period | Train PnL | Test PnL | Test WR | Test Trades | Test DD |
|---|---:|---:|---:|---:|---:|
| 1 | +167.45 | +20.09 | 61.5% | 13 | 37.35 |
| 2 | +192.30 | -7.11 | 50.0% | 6 | 49.11 |
| 3 | +241.57 | -69.37 | 33.3% | 9 | 78.39 |
| 4 | +237.77 | +20.79 | 66.7% | 6 | 6.95 |
| 5 | +223.36 | -71.76 | 18.2% | 11 | 69.09 |
| 6 | +59.05 | +16.48 | 75.0% | 4 | 23.35 |
| 7 | +116.88 | -1.71 | 50.0% | 4 | 3.81 |

## Summary

| Metric | Value |
|---|---:|
| Test periods | 7 |
| Positive test periods | 3/7 |
| Average test PnL | -13.23 USDT |
| Total test PnL | -92.59 USDT |
| Average train PnL | +176.91 USDT |
| Average train-test gap | +190.14 USDT |

## Comment

BTC alone still does not look reliable. Train periods are strong, test periods are weak. This pattern indicates that overfitting risk persists.

This result does not mean the strategy should be thrown out entirely; rather, it shows that parameters selected on BTC do not carry forward into the future. Therefore, it is more appropriate to look at the multi-symbol test: `docs/MULTI_SYMBOL.md`.

## Conclusion

Do not go live with BTC/USDT as a single symbol.

Priority:

1. Multi-symbol portfolio test.
2. Parameter stability map.
3. Monte Carlo trade-shuffle.
4. Testnet/paper trading.

## Reproduction

```bash
python walk_forward.py
```

Output: `walk_forward_results.csv`
