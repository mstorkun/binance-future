# Walk-Forward Analiz

**Amaç:** Optimize edilmiş parametrelerin gerçek piyasada (out-of-sample) çalışıp çalışmadığını ölçmek.

**Yöntem:** Veriyi 3 dönem'e böl. Her dönemde:
- Train (3000 bar / 18 ay): En iyi parametreleri bul
- Test (1000 bar / 6 ay): O parametrelerle performansı ölç

Bu, gerçek hayatta bot kurulurken yaşanacak şeyin tam simülasyonu: Geçmiş veriyle parametre seç, geleceğe uygula.

## Sonuçlar

| Dönem | Train Pencere | Test Pencere | Train PnL | Test PnL | Test WR | Test Trade |
|---|---|---|---|---|---|---|
| 1 | 2023-05 → 2024-09 | 2024-09 → 2025-02 | +47.1$ | **+35.4$** ✓ | %100 | 3 |
| 2 | 2023-10 → 2025-02 | 2025-02 → 2025-08 | +64.7$ | **-32.3$** ✗ | %50 | 4 |
| 3 | 2024-03 → 2025-08 | 2025-08 → 2026-01 | +102.8$ | **-7.6$** ✗ | %50 | 2 |

## Özet İstatistikler

| | Train | Test |
|---|---|---|
| Ortalama PnL | **+71.5$** | **-1.5$** |
| Karlı dönem | 3/3 | 1/3 |
| Train>Test farkı | — | **73$ (overfitting)** |

## Yorumlama

### Overfitting Kanıtı

Train'de ortalama +71.5$ kar, test'te ortalama -1.5$ zarar. Train ile test arasında 73$ fark var. Bu **klasik overfitting tablosu**:

- Stratejinin parametreleri geçmiş veriye fit oluyor
- Geleceğe uygulandığında bu fit dağılıyor
- Gerçek "edge" yok, sadece veri uydurması var

### İstatistiksel Yetersizlik

3 dönemden sadece 1'i karlı. Bu:
- Şans eseri olabilir
- 50% binom dağılımı altında p=0.5 (anlamsız)
- En az 10+ dönem gerekir anlamlı sonuç için

### Periyot 1 Anomalisi

Periyot 1 test'te **%100 win rate**. Ama sadece **3 trade**. Bu istatistiksel olarak anlamsız (varyans çok yüksek). 3 trade ile %100 WR'nin gerçek WR'nin %50 olma olasılığı hala %12.5'tir.

### Periyot 2-3 Çöküşü

İki ardışık dönemde test negatif. Strateji 2025-02 sonrasında çalışmamış. Olası nedenler:
- BTC volatilite rejimi değişimi (ETF sonrası düşük vol)
- Trend yapısının değişmesi (range-bound piyasa)
- Komisyon yükünün küçük PnL'leri yemesi

## Sonuç

Bu strateji **canlıda kullanılmamalı**. Overfitting kanıtı net.

## Yeniden Üretim

```bash
python walk_forward.py
```

Output: `walk_forward_results.csv`

## Daha İyi Test İçin

İlerleyen aşamalarda bu walk-forward iyileştirilebilir:
- Daha küçük roll (3 ay) → daha çok dönem
- Monte Carlo trade-shuffling → DD dağılımı
- Çoklu sembol üzerinden ağırlıklı ortalama
- Funding rate dahil
- Slippage'ı volatiliteye bağlı modelleme (yüksek vol = yüksek slip)
