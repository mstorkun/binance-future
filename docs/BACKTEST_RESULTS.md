# Backtest Sonuçları

Bu rapor güncel Donchian breakout mimarisi içindir. Eski EMA crossover sonuçları artık karar için kullanılmamalı.

## Model

- Sinyal: Donchian breakout.
- Filtreler: hacim, ADX, RSI, 1D EMA50 trend.
- Risk: ATR tabanlı SL, %2 işlem başı risk, 3x kaldıraç.
- Maliyetler: taker komisyon, slippage ve funding.

## BTC/USDT Düz Backtest

Son kayıtlı sonuç:

| Metrik | Değer |
|---|---:|
| İşlem | 86 |
| Win rate | %55.8 |
| Toplam PnL | +76.03 USDT |
| Max DD | 54.25 USDT |
| 3 yıl getiri | %7.60 |
| PnL/DD | 1.38 |

Yorum: BTC düz backtest pozitif ama zayıf. Walk-forward sonucu negatif olduğu için tek başına canlıya geçiş gerekçesi değildir.

## Çoklu Sembol Düz Backtest

`multi_symbol_results.csv` son kayıtlı özet:

| Sembol | İşlem | Win Rate | PnL | Max DD | Getiri |
|---|---:|---:|---:|---:|---:|
| BTC/USDT | 86 | %55.8 | +76.03 | 54.25 | %7.60 |
| ETH/USDT | 77 | %63.6 | +243.94 | 39.81 | %24.39 |
| SOL/USDT | 90 | %72.2 | +473.80 | 71.70 | %47.38 |
| BNB/USDT | 70 | %57.1 | +79.11 | 63.52 | %7.91 |

Bu düz backtest 4/4 pozitif, ancak düz backtest tek başına yeterli değildir. Ana karar walk-forward ve canlı/paper test ile verilmelidir.

## Funding Modeli

`backtest.py` artık opsiyonel tarihsel funding serisi kabul eder:

- Funding verisi varsa long/short yönüne göre signed funding hesaplanır.
- Funding verisi yoksa `config.DEFAULT_FUNDING_RATE_PER_8H` fallback olarak kullanılır.
- Bu fallback konservatiftir; gerçek funding bazen maliyet, bazen gelir olabilir.

## Monte Carlo Drawdown

Mevcut `backtest_results.csv` üzerinde 1000 trade-shuffle denemesi:

| Metrik | Değer |
|---|---:|
| PnL p05 | +76.03 USDT |
| PnL medyan | +76.03 USDT |
| PnL p95 | +76.03 USDT |
| DD medyan | 98.46 USDT |
| DD p95 | 160.81 USDT |
| DD max | 225.16 USDT |

Toplam PnL aynı trade seti karıştırıldığı için değişmiyor; asıl sinyal drawdown tarafında. BTC backtest'in tarihsel DD'si 54.25 USDT iken, sıra riski %95 senaryoda 160.81 USDT'ye çıkıyor. Bu nedenle canlı risk %2 yerine daha düşük başlamalı veya portföy/pozisyon limiti eklenmeli.

## Yeniden Üretim

```bash
python backtest.py
python multi_symbol_backtest.py
python monte_carlo.py --trades backtest_results.csv
```

Çıktılar:

- `backtest_results.csv`
- `multi_symbol_results.csv`
- `monte_carlo_results.csv`
