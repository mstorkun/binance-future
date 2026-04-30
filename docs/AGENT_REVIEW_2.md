# 5 Ajan İkinci Denetim — Donchian Breakout Stratejisi

**Tarih:** 2026-04-30
**Bağlam:** İlk denetim sonrası strateji EMA crossover'dan Donchian breakout'a geçirildi.
İlk Donchian sonuçları (+632 USDT, walk-forward 3/3 pozitif) çok iyi göründü — şüphe için
ikinci ajan turunu çalıştırdık.

---

## 1. Strateji Geçerliliği — Ajan 1

**Skor: 6/10**

- Donchian 20-bar BTC 4H için makul, Turtle System 1'e yakın ✓
- Volume 1.5×MA20 orta seviye filtre — Wyckoff standart 2.0× sıkı
- 1D EMA50 long/short-only ranging market'te bias yaratıyor — yumuşatılmalı
- Trailing %15 dar (literatürde %25-30 önerilir)
- **ADX hesaplanmış ama kullanılmıyor** — yatay piyasa filtresi eksik

**Önerileri uygulananlar:** ADX filtresi (`config.ADX_THRESH = 20`) eklendi.

---

## 2. Risk Yönetimi — Ajan 2

**Skor: 5/10**

- %2 per trade Kelly'ye göre çok muhafazakar (Kelly öneri: %14-27)
- 3x kaldıraç likidasyon riski sıfıra yakın ✓
- Trailing %15 değiştirme — backtest bu parametreyle kuruldu
- **`MAX_OPEN_POSITIONS=2` ölü parametre** (tek sembol kullanılıyor)
- Daily limit %3 vs per-trade %2 → 1.5 SL tampon, dar
- Funding rate backtest'te yok ❗

**Tehlike sırası:**
1. Trailing SL race condition
2. State recovery'de fake SL fiyatı
3. Funding/komisyon backtest'te eksik
4. Türkiye Binance hesap riski

---

## 3. Backtest Metodoloji & Kod — Ajan 3

**EN KRİTİK 3 BULGU:**

**[1] CRITICAL — Intra-bar SL/trail ordering bug**
`backtest.py:48-86` aynı bar içinde önce extreme=high güncellenip sonra SL kontrol ediliyordu. OHLC'de high/low sırası bilinmez — bu trailing SL'in olduğundan yüksek seviyeye taşınmasına ve daha az kayıpla çıkış kaydedilmesine yol açar. **Tipik etki: +%5-15 fazla PnL.**

**[2] HIGH — `add_daily_trend` look-ahead riski**
`indicators.py:80` shift mantığı doğru çıktı (`+1 day` 1D bar kapanışını sonra geçerli kılıyor) ama yorum yetersiz, edge-case test eksik.

**[3] HIGH — `bot.py:_recover_position` borsa SL'sini sorgulamıyor**
Restart sonrası ATR ile SL'i yeniden hesaplıyordu. Bot trailing'i yanlış noktadan günceller.

**Diğer:**
- Look-ahead Donchian shift(1) ✓ doğru
- Backtest entry timing ✓ doğru (bir bar gecikme, kasıtlı/konservatif)
- `walk_forward._override` try/finally ✓ var
- `set_leverage` başarısızsa pozisyon açılıyordu — abort eklenmeli

---

## 4. İstatistiksel Sağlamlık — Ajan 4

**Skor: 5.5/10**

- Train +644 vs Test +144 → ratio %22 (kabul: %40-60). **Overfitting var ama felaket değil.**
- 75 test trade Wilson %95 CI WR: [%56.7, %77.5] — geniş ama break-even üstü
- 3/3 pozitif p-değeri = 0.125 (anlamsız)
- One-sample t-test PnL>0: t=4.9, df=2, p≈0.039 — sınırda anlamlı, n=3 zayıf
- Test DD'leri 24/68/39 — std 18, worst-case μ+2σ ≈ 80 USDT
- P3'te parametre kayması (20→30) **kırmızı bayrak**

**"Promising, not proven."**

**Eksik testler:** Monte Carlo trade-shuffle, bootstrap CI, parametre stabilite haritası, daha çok WF dönemi (8+).

---

## 5. Real-World — Ajan 5

**Skor: 5/10**

**EN AGRESIF 3 RİSK (canlıda görülecek, backtest'te görünmüyordu):**

1. **Funding kanaması:** BTC perp ortalama %0.01/8h × 365×3 = %11/yıl ≈ 3 yılda 5-8 puan getiri buharlaşır
2. **State desync:** restart sonrası SL fake → çift SL veya yanlış SL = büyük kayıp
3. **Türkiye operasyonel:** hesap dondurma + USDT çekme = sermaye hapsi

**Slippage 5 bps yetersiz** — kırılım anlarında 10-30 bps gerçekçi. Modele 15 bps round-trip eklenmeli.

**Monitoring sıfır:** Telegram, healthcheck, heartbeat — hiçbiri yok.

---

# UYGULANAN DÜZELTMELER (kritik bug'lar)

| # | Bulgu | Dosya | Uygulandı |
|---|---|---|---|
| 1 | Intra-bar SL/trail ordering | `backtest.py` | ✅ SL kontrolü extreme update'inden ÖNCE |
| 2 | Funding rate eksik | `backtest.py` | ✅ %0.01/8h ortalama eklendi (~1 funding/4H bar) |
| 3 | Slippage 5 bps az | `backtest.py` | ✅ 15 bps round-trip yapıldı |
| 4 | Trailing SL race condition | `order_manager.py` | ✅ Önce yeni emir, sonra eski iptal |
| 5 | set_leverage başarısızsa açılıyor | `order_manager.py` | ✅ False dönerse pozisyon açma iptal |
| 6 | State recovery fake SL | `bot.py` | ✅ `fetch_active_sl` ile borsadan çekiyor |
| 7 | ADX filtresi kullanılmıyor | `strategy.py` | ✅ `bar["adx"] < ADX_THRESH` early return |
| 8 | stepSize precision | `order_manager.py` | ✅ `amount_to_precision()` |

---

# BUG FIX ÖNCESİ vs SONRASI

| Metrik | İlk Donchian | Bug fix sonra |
|---|---|---|
| Backtest 3 yıl PnL | +632 USDT | **+62.50 USDT** |
| Backtest WR | %70.6 | %54.7 |
| Backtest trade sayısı | 126 | 86 (ADX filtresi) |
| Walk-forward test ortalama | +144 USDT | **+6.8 USDT** |
| 3/3 test pozitif mi | 3/3 | 1/3 |

**Sonuç:** İlk +632 sayısı **iyimser intra-bar bias + eksik funding/slippage'tan geliyordu**. Gerçek strateji performansı çok daha mütevazı.

---

# KONSOLİDE VERDİKT

Strateji **canlıya hazır DEĞİL**:
- Yıllık ~%2 net getiri (3 yıl, BTC tek sembol)
- Walk-forward'da test ortalaması neredeyse sıfır
- Sadece P1 testi pozitif

Pozitif yan:
- Bug'lar bulundu ve düzeltildi → backtest artık güvenilir
- Mimari sağlam, atomik emir akışı çalışıyor
- ADX filtresi ile sinyal kalitesi arttı (trade sayısı düştü)

Sonraki şart:
1. Daha çok WF dönemi (8+, roll 3 ay)
2. Parametre stabilite haritası
3. Monte Carlo trade-shuffle (DD %95 worst-case)
4. Çoklu sembol test (ETH, SOL, BNB)
5. Volume eşik 1.5 → 1.8 deneme
6. Trailing %15 → %25 deneme

Bu adımlar olmadan canlı para kullanılmamalı.
