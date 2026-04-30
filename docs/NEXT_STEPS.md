# Sonraki Adımlar

Bu dosya güncel Donchian breakout + çoklu sembol mimarisi için karar listesidir.

## Tamamlananlar

- [x] EMA crossover bırakıldı.
- [x] Donchian breakout + hacim + 1D trend filtresi eklendi.
- [x] ADX ve RSI filtreleri eklendi.
- [x] Tek sembol backtest ve walk-forward güncellendi.
- [x] Çoklu sembol düz backtest eklendi.
- [x] Çoklu sembol walk-forward eklendi.
- [x] Backtest maliyetlerine komisyon, slippage ve funding dahil edildi.
- [x] Funding modeli tarihsel veri alabilecek şekilde genişletildi.
- [x] Monte Carlo trade-shuffle aracı eklendi.

## Şu Anki Karar

Canlı para ile çalıştırma yok.

Mevcut kanıt:

- BTC tek başına zayıf.
- ETH/SOL/BNB daha umut verici.
- Çoklu sembol walk-forward pozitif sinyal veriyor ama train-test farkı yüksek.

Bu yüzden bir sonraki aşama canlı değil, sağlamlık testidir.

## Öncelik 1: Parametre Stabilite Haritası

Amaç: Sonuç tek bir parametre noktasına mı bağlı, yoksa yakın parametrelerde de çalışıyor mu?

Test alanı:

- Donchian: 15, 18, 20, 22, 25, 30
- Volume multiplier: 1.2, 1.4, 1.5, 1.7, 2.0
- SL ATR: 1.5, 2.0, 2.5
- Semboller: ETH, SOL, BNB, BTC kontrol

Başarı kriteri:

- Sadece tek kombinasyon değil, yakın komşular da pozitif olmalı.
- SOL/ETH sonuçları tek bir aşırı optimize parametreye bağlı kalmamalı.

## Öncelik 2: Monte Carlo Sonuçlarını Sembollere Yay

Araç eklendi ve BTC `backtest_results.csv` için çalıştırıldı.

Komut:

```bash
python monte_carlo.py --trades backtest_results.csv
```

Çıktı:

- BTC tarihsel DD: 54.25 USDT.
- BTC Monte Carlo DD p95: 160.81 USDT.
- BTC Monte Carlo DD max: 225.16 USDT.

Yorum: İşlem sırası kötüleşince drawdown yaklaşık 3x büyüyebiliyor. Aynı test ETH/SOL/BNB için de üretilmeli.

## Öncelik 3: Paper/Testnet

Koşul:

- En az 1-2 ay.
- ETH/SOL/BNB ağırlıklı izleme.
- Her emir için gerçek fill, slippage ve funding kaydı.

Gerekli eksikler:

- Telegram/healthcheck alarmı.
- Reconnect/backoff.
- Açık pozisyon ve açık emir uyumsuzluğu alarmı.
- Çoklu sembol `bot.py` desteği.

## Canlıya Geçiş Kuralı

Ancak şu şartlarla:

- Testnet/paper sonuçları beklentiyle uyumlu.
- Maksimum DD Monte Carlo sınırının altında.
- Alarm ve acil durdurma mekanizması çalışıyor.
- İlk canlı sermaye 1000 USDT değil, 100-200 USDT.

## Bırakma Kuralı

Bot paper veya küçük canlı aşamada:

- 2 ay üst üste negatifse,
- Beklenen max DD'nin 2 katını aşarsa,
- Emir/state desync üretirse,

bot durdurulur ve strateji yeniden değerlendirilir.
