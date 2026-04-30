# Çoklu Sembol Test Sonuçları

**Soru:** Donchian breakout stratejisi BTC'ye özel mi, yoksa genel bir kenar (edge) mi?

**Yöntem:** Aynı parametre seti ile BTC, ETH, SOL, BNB üzerinde 3 yıllık backtest + walk-forward.
Düz backtest ve walk-forward tarihsel funding verisi kullanır; veri çekilemezse fallback varsayımına düşer.

---

## 1. Düz Backtest (3 yıl, aynı parametreler)

```
symbol     trades  win_rate  total_pnl   max_dd  pnl_pct  pnl_dd
BTC/USDT       86    %55.8      +76.03    54.25    %7.60    1.38
ETH/USDT       77    %63.6     +243.94    39.81   %24.39    5.98  ← güçlü
SOL/USDT       90    %72.2     +473.80    71.70   %47.38    6.52  ← çok güçlü
BNB/USDT       70    %57.1      +79.11    63.52    %7.91    1.23
```

**Özet:**
- 4/4 sembol pozitif PnL ✓
- Ortalama PnL: +218 USDT/sembol (3 yıl)
- En güçlü: SOL (+47% getiri)
- En zayıf: BTC, BNB (+6-7% getiri)

---

## 2. Walk-Forward (4 sembol × 7 dönem = 28 test penceresi)

Her dönem: 18 ay train + 3 ay test, 3 ay roll.

```
symbol     periods  train_avg  test_avg  test_total  test_pos  pos_ratio  test_dd_avg  overfit
BTC/USDT         7    +176.9   -13.2       -92.59        3       42.9%      38.3       +190
ETH/USDT         7    +167.8    +5.0       +35.24        4       57.1%      17.7       +163
SOL/USDT         7    +243.9   +13.7       +96.07        5       71.4%      17.2       +230
BNB/USDT         7    +110.8    +6.8       +47.71        4       57.1%      23.1       +104
```

**Özet:**
- 3/4 sembolde test ortalaması POZİTİF (sadece BTC negatif)
- 28 dönemden 16'sı pozitif (%57)
- En güvenilir: **SOL** (5/7 dönem pozitif, +13.7 ortalama, en düşük DD)
- En kötü: **BTC** (3/7 dönem pozitif, -13.2 ortalama)

---

## 3. Yorumlama

### İyi haber

- Donchian breakout BTC'ye özel **değil** — 4 sembolde de pozitif
- ETH/SOL/BNB BTC'den daha iyi performans gösteriyor (altcoinlerde trend daha kalıcı)
- SOL özellikle güçlü: %71 pozitif dönem, ortalama +13.7 USDT/dönem

### Kötü haber

- BTC tek başına yeterli değil — overfitting çok yüksek (+183 fark)
- Tüm sembollerde train>test farkı büyük (overfitting var)
- Test dönemlerinde DD artıyor (avg 18-39 USDT)

### Net Sonuç

> **Strateji gerçek bir kenar taşıyor olabilir**, ama kanıt henüz kesin değil.
> BTC zayıf; SOL/ETH daha umut verici. Canlı karar için parametre stabilitesi,
> Monte Carlo ve testnet/paper sonuçları beklenmeli.

---

## 4. Öneriler

### Seçenek A — SOL bot (en güçlü sembol)
```python
# config.py
SYMBOL = "SOL/USDT"
```
Backtest: +474 USDT, WF: 5/7 pozitif. Ama SOL volatilitesi yüksek, slippage daha kötü olabilir.

### Seçenek B — Portföy: ETH + SOL + BNB
1000 USDT'yi 3 sembole böl (333 USDT/sembol). Diversifikasyon avantajı.
- Düz backtest ortalaması: (+244 + 474 + 79) / 3 ≈ +266 USDT/sembol (3 yıl)
- Korelasyon riski: kripto coinleri birbirine ~0.85 korele, gerçek diversifikasyon sınırlı

### Seçenek C — BTC'yi tamamen at
BTC liste dışı. Sadece ETH/SOL/BNB.

**Tavsiyem: Seçenek B'yi testnet/paper aşamasında denemek** — canlı para kararı için erken.

---

## 5. Sonraki Test Adımları

Strateji "promising → çalışabilir" seviyesine çıktı. Ama hala şart:

1. **Parametre stabilite haritası** — donchian 18-22, vol 1.3-1.7 dene, gradient yumuşak mı?
2. **Monte Carlo trade-shuffle** — DD %95 worst-case ölç
3. **Çoklu sembol bot.py desteği** — şu an tek sembol
4. **Testnet 1-2 ay paper trading** — slippage/funding gerçek mi?
5. **Küçük canlı (200 USDT)** — 3 ay performans izlemesi
