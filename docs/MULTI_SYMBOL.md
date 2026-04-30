# Çoklu Sembol Test Sonuçları

**Soru:** Donchian breakout stratejisi BTC'ye özel mi, yoksa genel bir kenar (edge) mi?

**Yöntem:** Aynı parametre seti ile BTC, ETH, SOL, BNB üzerinde 3 yıllık backtest + walk-forward.

---

## 1. Düz Backtest (3 yıl, aynı parametreler)

```
symbol     trades  win_rate  total_pnl   max_dd  pnl_pct  pnl_dd
BTC/USDT       86    %54.7      +62.50    56.08    %6.25    1.09
ETH/USDT       77    %63.6     +237.80    40.15   %23.78    5.78  ← güçlü
SOL/USDT       90    %72.2     +470.65    72.11   %47.07    6.44  ← çok güçlü
BNB/USDT       70    %54.3      +69.88    64.14    %6.99    1.07
```

**Özet:**
- 4/4 sembol pozitif PnL ✓
- Ortalama PnL: +210 USDT/sembol (3 yıl)
- En güçlü: SOL (+47% getiri)
- En zayıf: BTC, BNB (+6-7% getiri)

---

## 2. Walk-Forward (4 sembol × 7 dönem = 28 test penceresi)

Her dönem: 18 ay train + 3 ay test, 3 ay roll.

```
symbol     periods  train_avg  test_avg  test_total  test_pos  pos_ratio  test_dd_avg  overfit
BTC/USDT         7    +168     -14.8      -103.65        3       42.9%      39.1       +183
ETH/USDT         7    +166      +4.4       +31.05        4       57.1%      17.8       +162
SOL/USDT         7    +241     +13.4       +93.74        5       71.4%      17.3       +228
BNB/USDT         7    +105      +6.0       +42.18        4       57.1%      23.2       +100
```

**Özet:**
- 3/4 sembolde test ortalaması POZİTİF (sadece BTC negatif)
- 28 dönemden 16'sı pozitif (%57)
- En güvenilir: **SOL** (5/7 dönem pozitif, +13.4 ortalama, en düşük DD)
- En kötü: **BTC** (3/7 dönem pozitif, -14.8 ortalama)

---

## 3. Yorumlama

### İyi haber

- Donchian breakout BTC'ye özel **değil** — 4 sembolde de pozitif
- ETH/SOL/BNB BTC'den daha iyi performans gösteriyor (altcoinlerde trend daha kalıcı)
- SOL özellikle güçlü: %71 pozitif dönem, ortalama +13 USDT/dönem

### Kötü haber

- BTC tek başına yeterli değil — overfitting çok yüksek (+183 fark)
- Tüm sembollerde train>test farkı büyük (overfitting var)
- Test dönemlerinde DD artıyor (avg 18-39 USDT)

### Net Sonuç

> **Strateji gerçek bir kenar (edge) taşıyor**, ama **BTC'de zayıf**.
> Sadece BTC'ye uygulamak yanıltıcı sonuç verir. SOL/ETH öncelikli olmalı.

---

## 4. Öneriler

### Seçenek A — SOL bot (en güçlü sembol)
```python
# config.py
SYMBOL = "SOL/USDT"
```
Backtest: +470 USDT, WF: 5/7 pozitif. Ama SOL volatilitesi yüksek, slippage daha kötü olabilir.

### Seçenek B — Portföy: ETH + SOL + BNB
1000 USDT'yi 3 sembole böl (333 USDT/sembol). Diversifikasyon avantajı.
- Beklenen kâr: ortalama (+237 + 470 + 70) / 3 ≈ +260 USDT/sembol × 3 = ~780 USDT (3 yıl)
- Korelasyon riski: kripto coinleri birbirine ~0.85 korele, gerçek diversifikasyon sınırlı

### Seçenek C — BTC'yi tamamen at
BTC liste dışı. Sadece ETH/SOL/BNB.

**Tavsiyem: Seçenek B** — testnet'te 3 sembol portföyü, sonra canlıda ETH+SOL ağırlıklı.

---

## 5. Sonraki Test Adımları

Strateji "promising → çalışabilir" seviyesine çıktı. Ama hala şart:

1. **Parametre stabilite haritası** — donchian 18-22, vol 1.3-1.7 dene, gradient yumuşak mı?
2. **Monte Carlo trade-shuffle** — DD %95 worst-case ölç
3. **Çoklu sembol bot.py desteği** — şu an tek sembol
4. **Testnet 1-2 ay paper trading** — slippage/funding gerçek mi?
5. **Küçük canlı (200 USDT)** — 3 ay performans izlemesi
