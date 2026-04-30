# Backtest Sonuçları

**Veri:** BTC/USDT 4H, Mayıs 2023 - Nisan 2026 (3 yıl, 6570 bar)

## Bug Düzeltmesi Öncesi/Sonrası

| Metrik | Önce (bug'lı) | Sonra (gerçek) |
|---|---|---|
| Toplam işlem | 57 | 46 |
| Win rate | %60 | %76 |
| Toplam PnL | **+1016 USDT** | **+131 USDT** |
| Yıllık getiri | ~%33 | ~%4.4 |
| Max DD | 385$ (%38) | 35$ (%3.5) |
| PnL/DD oranı | 2.6 | 3.7 |

**PnL %87 düştü** (1016 → 131). Wilder smoothing + leverage bug + komisyon/slippage düzeltmeleri.

## En İyi Konfigürasyon

```python
SL_ATR_MULT      = 1.5
TRAIL_GIVEBACK   = 0.15
TRAIL_ACTIVATE   = 0.0   # ATR çarpanı (0 = anında aktive)
ADX_THRESH       = 20
LEVERAGE         = 3
RISK_PER_TRADE   = 0.02
```

## Optimize Top-10 (108 kombinasyon)

```
trades  win_rate  total_pnl  max_dd  sl_mult  trail_giveback  trail_activate  adx
    46    %76.1    131.06    34.66    1.5     0.15            0.0             20
    46    %76.1    109.67    35.23    1.5     0.20            0.0             20
    21    %76.2     65.05    22.39    2.0     0.15            0.0             25
    21    %71.4     67.70    24.98    1.5     0.15            0.0             25
    21    %76.2     57.88    22.41    2.0     0.20            0.0             25
    46    %78.3     89.95    35.39    2.0     0.15            0.0             20
    46    %80.4     80.53    32.52    2.5     0.15            0.0             20
    21    %71.4     58.56    26.53    1.5     0.20            0.0             25
    21    %76.2     47.48    21.88    2.5     0.15            0.0             25
    61    %78.7     74.59    35.74    2.5     0.15            0.0             18
```

## Sonuçların Yorumu

**İyi yan:**
- Win rate %76 yüksek
- Max DD %3.5 düşük (sermaye koruma çalışıyor)
- 3 yıl pozitif PnL

**Kötü yan:**
- Yıllık ~%4.4 getiri kripto riski için düşük (kripto volatilitesi >%50)
- 46 işlem 3 yılda istatistiksel olarak zayıf
- Walk-forward'ta out-of-sample **negatif** ([WALK_FORWARD.md](WALK_FORWARD.md))

## Komisyon ve Slippage Detayı

Backtest'te her işlem PnL'sinden düşülüyor:

```python
notional = (entry + exit_price) * size
commission_and_slippage = notional * 0.0009  # %0.04 komisyon × 2 + %0.05 slippage
```

Tipik trade nominali ~1500-2000 USDT, gider başına ~1.5-2 USDT.
46 trade × ~1.7 USDT = **~78 USDT toplam gider** (raporlanan PnL'den düşülmüş halde).

## Yeniden Üretim

```bash
python backtest.py     # Tek konfig (config.py)
python optimize.py     # 108 kombinasyon tarama
python walk_forward.py # Out-of-sample doğrulama
```

Sonuç dosyaları:
- `backtest_results.csv`
- `walk_forward_results.csv`
