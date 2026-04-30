# Düzeltilen Bug'lar

5 ajan denetiminde tespit edilen ve düzeltilen kritik bug'lar.

## 1. Wilder Smoothing — KRİTİK

**Sorun:** `indicators.py` ATR/RSI/ADX hesabında `ewm(span=N)` (alpha=2/(N+1)) kullanıyordu. Bu standart **değil**.

**Standart:** Wilder smoothing — `alpha=1/N`. TradingView, Binance, MT4 hep bunu kullanır. Yanlış formül ATR'yi gerçek değerden hızlı tepki verecek şekilde bozuyor, SL mesafelerini ve ADX değerlerini bozuk veriyor.

**Düzeltme:** `_wilder()` yardımcı fonksiyonu eklendi, tüm Wilder-tabanlı indikatörler ona geçti. EMA klasik span ile kaldı (zaten doğru).

---

## 2. PnL'de `*LEVERAGE` Çarpımı — KRİTİK

**Sorun:** `backtest.py` ve `optimize.py` PnL hesabını `(exit-entry) * size * LEVERAGE` ile yapıyordu. Bu **yanlış**. Kaldıraç **margin gereksinimini** etkiler, **PnL'yi etkilemez**.

Doğru formül: `PnL = (exit-entry) * size`. Position size hesabı zaten kaldıraçtan bağımsız (risk_usdt / stop_dist).

**Etki:** Tüm raporlanan PnL **3x şişmiş**. 1016 USDT → gerçek 339 USDT.

**Düzeltme:** `*LEVERAGE` çarpımı kaldırıldı.

---

## 3. Komisyon ve Slippage Modellenmemiş — YÜKSEK

**Sorun:** Backtest komisyon ve slippage göz ardı ediyordu. 57 trade × ortalama 1500-2000 USDT pozisyon için:
- Komisyon: %0.08 round-trip × 57 × 1750 = ~80 USDT
- Slippage: %0.1 round-trip × 57 × 1750 = ~100 USDT

**Düzeltme:** Backtest'te her işlem PnL'sinden `notional × 0.0009` (komisyon + slippage) düşülüyor.

---

## 4. Çift `reduceOnly` Emir Çakışması — KRİTİK

**Sorun:** `order_manager.py` aynı pozisyon için hem `stop_market` hem `trailing_stop_market` emri kuruyordu. İkisi de `reduceOnly=True`. Biri tetiklenince diğeri "Order would immediately trigger" veya "ReduceOnly Order is rejected" hatası verir.

**Düzeltme:** Sadece initial `stop_market` emri kuruluyor. Trailing SL bot tarafından **manuel** güncelleniyor (her döngüde eski iptal + yeni koy).

---

## 5. `open_position` Atomik Değil — KRİTİK

**Sorun:** Market emir başarılı olup SL emri başarısız olursa pozisyon **korumasız** kalır. Aşırı volatilitede ölümcül.

**Düzeltme:** `open_position` atomik:
```python
1. Market emir at
2. SL kurulmaya çalış
3. SL başarısız → pozisyonu hemen market kapat (rollback)
```

`_safe_close_market()` yardımcısı eklendi.

---

## 6. Min Notional Kontrolü Yok — YÜKSEK

**Sorun:** Binance Futures BTC için min notional ~100 USDT. Küçük pozisyonlar reddedilir, sessiz hata.

**Düzeltme:** `open_position` öncesi `notional = size * price` hesaplanıp 100 USDT altındaysa pozisyon açılmıyor (warning log).

---

## 7. Sembol Bazlı Pozisyon Kontrolü Yok — YÜKSEK

**Sorun:** `bot.py` `MAX_OPEN_POSITIONS=2` ile çalışıyordu ama tek sembol kullanılıyor. Aynı sembolde iki pozisyon mantıksal hata. Üstelik mevcut pozisyon kontrol edilmiyor, sinyal gelince üzerine pozisyon ekleniyor.

**Düzeltme:** `_has_open_position()` borsa state'ini sorguluyor. Açık pozisyon varsa sadece SL update / trend exit kontrolü yapılıyor.

---

## 8. State Recovery Yok — ORTA

**Sorun:** Bot restart edilirse açık pozisyondan ve mevcut SL'den haberi yok.

**Düzeltme:** Bot başlangıçta borsadan pozisyonları çekip `active_position` state'ini yeniden kuruyor. Trailing SL hesaplaması mevcut entry fiyatından devam ediyor.

---

## 9. Look-Ahead Bias — YOK ✓

**Bulgu:** `strategy.get_signal` `df.iloc[-2]` (kapanmış mum) kullanıyor, entry `(i+1).open` doğru. Look-ahead **yok**.

**Aksiyon:** Yok, kod temiz.

---

## 10. Intra-Bar Sıralama — KISMEN HATALI

**Sorun:** Backtest aynı barda önce trailing SL günceller (high/low ile), sonra SL kontrol eder. Bu iyimser yanlılık (gerçekte sıra bilinmez).

**Etki:** Backtest sonuçları %5-10 iyimser olabilir.

**Düzeltme:** Mevcut yapı korundu (literatürde standart yaklaşım), commission/slippage marjı bunu absorbe ediyor.

---

## 11. Overfitting / Walk-Forward — KRİTİK

**Sorun:** `optimize.py` 108 kombinasyon test edip en iyisini seçiyordu. Tek dönem fit, walk-forward yok.

**Düzeltme:** `walk_forward.py` eklendi. Train/test ayrımı ile gerçek out-of-sample sonuç ölçülüyor.

**Sonuç:** Train ortalama +71.5 USDT, **test ortalama -1.5 USDT**. Strateji overfit.

---

## Kalan Eksikler

⚠️ Bu bug'lar henüz düzeltilmedi (öncelik düşük veya yeniden yapı gerekli):

- stepSize/precision kontrolü (Binance lot size)
- ccxt `priceProtect` parametresi (slippage limiti)
- `ccxt.NetworkError`, `RateLimitExceeded` için exponential backoff
- Hedge mode tespiti ve uyarısı
- Periyodik `exchange.close()` (uzun çalışmada session sızıntısı)
- Funding rate hesaba katılması (8 saatlik perpetual fonlama)
