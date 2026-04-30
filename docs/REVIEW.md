# 5 Ajan Denetim Raporu

**Tarih:** 2026-04-30
**Denetleyen:** Claude Sonnet 4.6 — paralel 5 ajan
**Durum:** Tamamlandı, kritik bug'ların büyük çoğunluğu düzeltildi.

---

## Bağlam

İlk backtest sonucu (3 yıllık BTC 4H, optimize edilmiş parametreler):
- 57 işlem · %60 win rate · **+1016 USDT (3 yılda %100 getiri)** · Max DD 385$

Bu sonuç şüpheli görüldü. 5 ajan paralel olarak farklı açılardan denetim yaptı.

---

## Ajan 1 — Strateji Geçerliliği

**Bulgular:**
- Strateji mantığı klasik (EMA + ADX + RSI), 57 trade/3 yıl istatistiksel olarak zayıf
- `strategy.py:26-27` flipped koşulu çok katı — kesişim anında ADX/RSI uygun değilse trend boyunca tekrar girilmez
- `config.py:31` RSI_SHORT 30-60 asimetrik (long 40-70 ile uyumsuz)
- `indicators.py` EMA span yerine **Wilder smoothing** olmalıydı (ADX/RSI/ATR yanlış kalibre)
- Volume filtresi yok, daha yüksek TF onayı yok

**Öneri:** Wilder düzeltmesi sonra backtest tekrar — mevcut sonuçlar yanıltıcı.

---

## Ajan 2 — Risk Yönetimi

**Tehlike sıralaması:**

1. **KRİTİK** — Min notional / stepSize kontrolü yok (`risk.py`). Binance reddi gelir.
2. **KRİTİK** — Slippage, partial fill, reconnect, state recovery yok (`bot.py`)
3. **YÜKSEK** — Max DD %38 retail için kabul edilemez (endüstri std %15-20)
4. **ORTA** — Günlük kayıp %3 limiti per trade %2 ile çelişkili (2 SL = %4)
5. **DÜŞÜK** — Kaldıraç 3x güvenli (BTC 4H'de %33 ters hareket görülmemiş)
6. **DÜŞÜK** — Per trade %2 sınırda, Kelly %1-1.5 öneriyor

**Acil aksiyon:** minQty/minNotional guard, reconnect/state-recovery, risk %2→%1.5, daily limit %3→%2.5.

---

## Ajan 3 — Kod Kalitesi

**En kritik 3 bulgu:**

1. **Wilder yerine EMA span** (`indicators.py`) → tüm indikatörler yanlış
2. **`open_position` atomik değil** (`order_manager.py:23-53`) — SL kurulamazsa pozisyon korumasız + çift `reduceOnly` emir çakışıyor
3. **Bot pozisyon kontrolü hatalı** (`bot.py:51-54, 79`) — aynı sembolde tekrar pozisyon açılabilir

**Diğer:**
- 4. Look-ahead bias YOK — temiz
- 11. **Pozisyon hesabında `*LEVERAGE` çarpımı YANLIŞ** — kaldıraç sadece margin'i etkiler, PnL **3x şişiyor**
- 7. Network/rate-limit handling yok, exponential backoff yok
- 8. Testnet URL override gereksiz, `set_sandbox_mode` yeterli
- 12. `optimize.py` thread-unsafe (config attribute mutation)

---

## Ajan 4 — Backtest Metodolojisi

**Reel mi, illüzyon mu?**

| Kalem | Etki |
|---|---|
| Komisyon (taker %0.04 × 2) | -91 USDT |
| Slippage (5-15 bps) | -23 USDT |
| Spread | -6 USDT |
| **Toplam giderler** | **~-120 USDT** |
| Look-ahead bias | YOK ✓ |
| Intra-bar sıralama | İyimser yanlılık (high/low sırası varsayılmış) |
| Overfitting | 108 kombinasyon test → en iyi seçim = klasik selection bias |
| Survivorship | Sadece BTC, sadece 4H |
| Rejim karışımı | 2023 yatay, 2024 boğa, 2025 düzeltme — kâr 2024'te yoğunlaşmış |

**Yaklaşık düzeltme:**
- Raporlanan: 1016 USDT
- Leverage düzeltmesi: 1016 ÷ 3 = ~339
- Komisyon + slippage: 339 - 120 = ~220
- Overfitting deflate (%30-50): **~110-160 USDT (yıllık ~%4-5)**

**Sonuç:** Sayıların ~%60'ı reel, ~%40'ı illüzyon.

---

## Ajan 5 — Parametre Sağlamlığı

**Sağlamlık skoru: 3/10**

- Üst 10 konfigürasyonda PnL 488-1016 arası salınıyor (%108 fark) → gradient yumuşak değil
- `trail_giveback=0.15` kümeleşmesi: tek yönde test, kenar etkisi → veri-spesifik
- `trail_activate` 0.0 → 1.0 dramatik PnL değişimi (488 → 897) → farklı rejim
- Win rate %54-81 dalgalanma → kırmızı bayrak
- 57 trade istatistiksel zayıf, %95 CI ±%13
- p-hacking riski: 108 kombinasyondan 5-10'u şansla iyi görünür
- **Walk-forward yok, out-of-sample yok** → ölümcül eksiklik

**Verdikt:** "Umut verici hipotez", "deploy edilebilir sistem" değil.

---

## Konsolide Aksiyon Listesi

Aşağıdaki düzeltmeler yapıldı, detay: [BUGS_FIXED.md](BUGS_FIXED.md)

✅ 1. Wilder smoothing (`indicators.py`)
✅ 2. PnL formülünde `*LEVERAGE` kaldırıldı
✅ 3. Komisyon (%0.04 × 2) + slippage (5 bps × 2) eklendi
✅ 4. `open_position` atomik açma + rollback
✅ 5. Çift SL emir kaldırıldı
✅ 6. Min notional kontrolü
✅ 7. Sembol bazlı pozisyon kontrolü
✅ 8. State recovery (bot restart sonrası)
✅ 9. Walk-forward analizi (`walk_forward.py`)

⚠️ Kalan: stepSize kontrolü, slippage/priceProtect, reconnect/backoff, hedge mode kontrolü, exchange.close() periyodik.
