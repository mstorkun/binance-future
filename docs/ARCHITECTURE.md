# Sistem Mimarisi

## Bileşen Diyagramı

```
                     ┌─────────────────┐
                     │     bot.py      │  Ana döngü (canlı çalışma)
                     │  schedule.run() │
                     └────────┬────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐         ┌─────────────┐       ┌────────────┐
   │ data.py │         │ strategy.py │       │   risk.py  │
   │ (ccxt)  │         │ get_signal  │       │ pos_size   │
   └────┬────┘         │ check_exit  │       │ sl_tp      │
        │              │ trail_stop  │       │ daily_lim  │
        │              └──────┬──────┘       └──────┬─────┘
        │                     │                     │
        │                     ▼                     │
        │              ┌──────────────┐             │
        │              │indicators.py │             │
        │              │ EMA  Wilder  │             │
        │              │ ADX  RSI ATR │             │
        │              └──────────────┘             │
        │                                           │
        ▼                                           ▼
   ┌──────────────┐                          ┌─────────────────┐
   │ Binance API  │  ◄────────────────────── │ order_manager.py│
   │              │      market/stop emir     │ open_position  │
   │              │                           │ update_trail   │
   │              │                           │ close_market   │
   └──────────────┘                           └─────────────────┘
```

## Veri Akışı (Canlı Bot)

```
Her saatte bir (4H mum kapanışını yakalamak için):

1. data.fetch_balance()        → bakiye
2. data.fetch_ohlcv()          → son 200 mum
3. indicators.add_indicators() → EMA, ADX, RSI, ATR ekle
4. _has_open_position()        → borsadan açık pozisyon sorgu

5a. AÇIK POZİSYON VAR:
    - strategy.check_exit() → trend tersine döndü mü?
        → Evet → close_position_market() + state temizle
        → Hayır → trailing SL güncelle
            (extreme = max/min güncelle)
            (yeni SL eskiden iyiyse → cancel + new stop_market)

5b. AÇIK POZİSYON YOK:
    - strategy.get_signal() → LONG/SHORT/None
        → None → çık
        → Var → om.set_leverage() → om.open_position()
            (atomik: market + stop_market, başarısız → rollback)
            (active_position state'i kaydet)

6. risk.daily_loss_exceeded() → günlük limit aşıldı mı?
    → Evet → close_all() ve dur
```

## Veri Akışı (Backtest)

```
1. fetch_long_history(years=3)  → 3 yıl 4H veri (6570 bar)
2. indicators.add_indicators() → indikatörleri ekle
3. for each bar:
    - get_signal(window) → sinyal var mı?
    - Var ise: bir sonraki barın open'ında giriş simüle et
    - İlerleyen barlarda:
        - trend ters → kapatma
        - trailing SL hit → kapatma
    - PnL hesapla, komisyon + slippage düş
4. CSV'ye yaz, özet raporla
```

## Veri Akışı (Walk-Forward)

```
1. 6570 bar veri çek
2. for period in 3:
    - train_window = bar[start : start + 3000]
    - test_window  = bar[start + 3000 : start + 4000]
    - find_best_params(train_window) → 54 kombinasyon test
    - run_segment(test_window, best_params) → out-of-sample
    - sonucu kaydet
    - start += 1000
3. Train ortalama vs test ortalama karşılaştır
```

## State Management

**Bot state (`bot.py`):**
- `active_position`: dict | None
  - `side`: "long" / "short"
  - `entry`: float
  - `sl`: float (trailing güncellendikçe değişir)
  - `size`: float (kontrat)
  - `extreme`: float (long için max, short için min)
- `daily_start_bal`: float | None (UTC 00:01'de sıfırlanır)

**Borsa state:**
- `exchange.fetch_positions(SYMBOL)` — otorite kaynak
- Bot her döngüde borsa state'ini sorguluyor, kendi state'ini ona göre senkronize ediyor (drift önleme)

## Kritik Tasarım Kararları

### 1. Trailing SL — Bot Tarafında Manuel

**Alternatif:** Binance'in `TRAILING_STOP_MARKET` emir tipi.

**Seçilen:** Bot her döngüde eski SL'i iptal edip yenisini koyar.

**Sebep:** Binance'in trailing emri callback rate'e dayanıyor (yüzde). Bizim kuralımız "kazancın %15'ini geri ver" dinamik (her bar yeniden hesap). Manuel kontrol daha esnek.

**Risk:** Cancel + create arasında borsa fiyat hareketi olursa pozisyon korumasız kalır. ~50ms pencere. Düşük risk.

### 2. Atomik Pozisyon Açma + Rollback

**Alternatif:** Sırayla emir → SL → trailing.

**Seçilen:** Market emir, sonra SL, başarısızsa market kapat.

**Sebep:** Crypto'da volatilite spike'larında SL emri reddedilebilir. Pozisyon korumasız kalmamalı.

### 3. Wilder Smoothing

**Alternatif:** EMA span (kolay).

**Seçilen:** Wilder (`alpha=1/N`).

**Sebep:** Standart RSI/ADX/ATR Wilder kullanır. Span kullanmak indikatörleri TradingView, Binance ile uyumsuz hale getiriyordu.

## Test Stratejisi

| Test Türü | Yöntem | Amaç |
|---|---|---|
| Geçmiş veri backtest | `backtest.py` | Strateji çalışıyor mu? |
| Parametre tarama | `optimize.py` | En iyi parametreler? |
| Walk-forward | `walk_forward.py` | Overfitting var mı? |
| Testnet (Binance) | `bot.py` + testnet | Canlı emir mantığı çalışıyor mu? |
| Canlı (küçük sermaye) | `bot.py` + canlı | Gerçek slippage/funding ne? |

## Bağımlılıklar

```
ccxt>=4.2.0       # Binance API
pandas>=2.0.0     # Veri/indikatör
schedule>=1.2.0   # Zamanlayıcı
python-dotenv     # .env yükleme
```

`pandas-ta` ve `numba` kullanılmıyor — saf pandas yeterli, kurulum kolay.
