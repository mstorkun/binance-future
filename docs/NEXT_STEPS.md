# Sonraki Adımlar

Walk-forward analiz EMA crossover stratejisinin canlıda çalışmadığını gösterdi. Üç yol var.

## Karar: Birleşik Yaklaşım

Önerilen: **Donchian breakout (ana sinyal) + hacim filtresi + günlük TF onayı + çoklu sembol**.

### Neden EMA Crossover Bırakılıyor

- Walk-forward overfitting kanıtladı
- EMA crossover gecikmeli — sinyal geldiğinde trendin önemli kısmı kaçmış oluyor
- Kripto'da yatay piyasa daha sık görülüyor — crossover whipsaw'a açık

### Neden Donchian Breakout

- Turtle Trader benzeri, literatürde trend takip için crossover'dan üstün
- N-bar high/low kırılımı net giriş/çıkış kuralı
- Kriptoda momentum kırılımları sıkça başarılı oluyor (manipülasyon, halving, ETF haberleri)

### Sinyal Hiyerarşisi

```
1. 1D EMA 50 yönü        → trend filtresi (yüksek TF onayı)
   - 1D fiyat > EMA 50  → sadece long sinyaller
   - 1D fiyat < EMA 50  → sadece short sinyaller

2. 4H Donchian 20         → kırılım sinyali
   - 4H high > 20-bar high → potansiyel LONG
   - 4H low  < 20-bar low  → potansiyel SHORT

3. 4H Hacim filtresi      → kırılım gerçek mi?
   - Bar hacmi > 20-bar avg × 1.5 → onayla
   - Düşük hacim kırılımı → reddet (false breakout)

4. ATR çıkış              → mevcut sistem korunur
   - Initial SL: 2 × ATR
   - Trailing: kazancın %15'i geri (mevcut)
   - Donchian 10-bar low/high (chandelier exit) — alternatif çıkış
```

## Aşamalı Plan

### Faz 1: Yeni Strateji Implementasyonu

- [ ] `strategy.py` Donchian breakout + hacim + 1D filtresi
- [ ] `indicators.py` Donchian channel (rolling max/min) eklensin
- [ ] `data.py` 1D timeframe verisi de çekilsin (`fetch_ohlcv_multi_tf`)
- [ ] Backtest adapte
- [ ] Optimize parametre tarama (Donchian period, vol mult, EMA period)

### Faz 2: Çoklu Sembol

- [ ] `config.py` SYMBOLS listesi (BTC, ETH, SOL, BNB)
- [ ] `bot.py` her sembol için ayrı pozisyon takibi
- [ ] Risk per trade artık portföy bazlı: `total_risk = N × per_trade`
- [ ] Sembol başına max pozisyon, toplam max pozisyon

### Faz 3: Walk-Forward + Robust Test

- [ ] Yeni strateji ile walk-forward (3+ dönem)
- [ ] Çoklu sembolde test (BTC + ETH + SOL portföy)
- [ ] Monte Carlo trade-shuffling (DD dağılımı)
- [ ] Funding rate dahil edilmesi

### Faz 4: Canlı Hazırlık

- [ ] Testnet'te 2-3 hafta paper trading
- [ ] stepSize, priceProtect, reconnect/backoff eksikleri
- [ ] Funding fee tracking (8h once)
- [ ] Telegram alert (her trade ve hata için)
- [ ] Performans dashboard (Grafana / basit web)

### Faz 5: Canlı

- [ ] 100-200$ ile başla (1000$ değil)
- [ ] 1 ay performans izleme
- [ ] Ölçeklenme: tahmin edilen DD'nin 4x katı sermaye

## Beklentiler

Bu yapı ile gerçekçi yıllık getiri hedefi: **%15-30** (kripto trend takibi için makul).

%50+ getiri vaat eden bot satıcıları **dolandırıcıdır**.

## Bilinmeyen Riskler

- 2026 sonrası kripto rejimi belirsiz
- Binance regülasyon değişiklikleri (Türkiye için özel risk)
- Stratejik AI bot rekabeti (mevcut ML botlar bizimkinin kâr alanını yiyebilir)
- Funding rate negatif spike'lar (long-heavy piyasada)

## Gerekirse Bırakma Kuralı

Bot canlıda 2 ay içinde:
- Test ortalaması negatifse,
- Veya max DD beklenenin 2x'ini aşarsa,

→ Botu durdur, geri dön ve yeniden değerlendir. Sermaye koruma her zaman kâr beklentisinden önce gelir.

## Reçete: Yeni AI'a Devir

Bu reponun başka bir AI tarafından devralınması durumunda:

1. **İlk 30 dk:** [README.md](../README.md), [REVIEW.md](REVIEW.md), [BUGS_FIXED.md](BUGS_FIXED.md) okumak
2. **Sonra:** [BACKTEST_RESULTS.md](BACKTEST_RESULTS.md) ve [WALK_FORWARD.md](WALK_FORWARD.md) — sonuçları gör
3. **Sonra:** Bu dosya — yön
4. **Kod:** [ARCHITECTURE.md](ARCHITECTURE.md) — sistem haritası

Önce dökümanları oku, sonra koda dokun.
