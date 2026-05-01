# Kritik Denetim — Claude 10 Uzman Ajan Sentezi (2026-05-01)

> **Not:** Bu rapor `binance-bot` reposu üzerinde paralel çalıştırılan 10 uzman alt-ajanın (strateji, risk, backtest, execution, Binance API, mimari, state/recovery, quant/istatistik, ops/güvenlik, trader perspektifi) bağımsız bulgularının sentezidir. Codex aktif çalışırken read-only modda yapılmıştır; `order_manager.py`, `tests/test_safety.py`, `walk_forward_results.csv`, `exchange_filters.py` dosyalarına yazma yapılmamıştır.
>
> Codex'in `docs/CRITICAL_AUDIT_2026_05_01.md` dosyası ile birlikte okunmalıdır — Codex'in triage notlarına bu raporun bulguları kaynak teşkil etmektedir.

---

## TL;DR (acımasız özet)

10 ajandan 10'unun konsensüsü: **Bu bot canlı para görmemeli.** Edge ya yok ya da slippage + funding + komisyonun altına düşecek kadar küçük. Gerçekçi 12-aylık net beklenti **-%5 ile +%10** arasında, medyan ~%0-3 — yani Binance USDT Earn (%4-8) bunu aşar, sıfır operasyonel riskle.

Backtestteki %79 / %124 CAGR rakamları **istatistiksel olarak savunulamaz**:
- Walk-forward sahte (parametre seçimi yapılmıyor)
- Sembol seçimi (DOGE/LINK/TRX) 455 kombinasyondan in-sample cherry-pick
- Monte Carlo varsayımları kırık (IID, path-bağımsız)
- Slippage iyimser (sabit 15 bps), funding modeli yetersiz

Production katmanı (alerting yok, secret yönetimi yarım, margin/position mode set edilmiyor, `priceProtect="TRUE"` string bug, recvWindow/timesync yok) okul projesi seviyesinde.

---

## 1. Ajan Konsensüsü — 10/10 Anlaştı

| Bulgu | Etki | Kanıt |
|---|---|---|
| **Walk-forward sahte** — parametre seçimi train segmentinde yapılmıyor, tüm WF aynı sabit parametrelerle | "7/7 pozitif fold" anlamsız | `walk_forward.py:148`, `portfolio_walk_forward.py:97-111` |
| **Sembol cherry-pick** — DOGE/LINK/TRX 455 kombinasyondan #1; Bonferroni yok | CAGR %124 iddiası p-hacking | `portfolio_candidate_sweep_results.csv` |
| **In-sample → OOS uçurum %50-99** | BTC tek sembol WF: train +5773 USDT, test +43 USDT | `walk_forward_results.csv`, `multi_symbol_walk_forward_results.csv` |
| **Monte Carlo IID kırık** — bootstrap path-bağımsız, kripto vol clustering ihlal | "Loss probability 0.0%" fiziksel olarak imkânsız | `monte_carlo.py:35-100` |
| **Slippage iyimser** — sabit 15 bps; flash crash'te 100-500 bps | Düşük likidite altcoinde 30-100 bps gerçekçi | `config.py:169` |
| **Funding modeli yetersiz** — 3 yılda toplam ~33 USDT | Tarihsel realite -%5 ile -%15/yıl | `portfolio_trades_growth_70_compound.csv` |
| **Sharpe / Sortino YOK** | Sadece raw CAGR + Calmar | grep: `sharpe`/`sortino` yok |
| **Test coverage çöl** — 1 dosya, strategy/risk/order_manager için 0 unit test | ~7000 LoC kod / 580 LoC test | `tests/test_safety.py` |

---

## 2. En Öldürücü 5 Bug (canlıda hesabı patlatır)

1. **`LIQUIDATION_GUARD_ENABLED = False` + `PROTECTIONS_ENABLED = False`** — iki kritik koruma kapalı, 10x kaldıraçta SL yetişmezse tüm wallet gider.
   - `config.py:70`, `config.py:129`

2. **Live state RAM-only** — `bot.py`'de `active_positions` diske yazılmıyor; crash sonrası `extreme` (trailing high) entry'ye reset → kazanılan trail kaybediliyor + soft SL geri açılıyor.
   - `bot.py:51`, `bot.py:100`

3. **`priceProtect="TRUE"` string bug** — Binance bool bekler, ccxt sürümüne göre sessiz fail veya `-1102` reject.
   - `execution_guard.py:41`

4. **Margin mode + position mode hiç set edilmiyor** — kullanıcı borsada ISOLATED bıraktıysa liquidation formülü tamamen yanlış (cross-mode varsayar); HEDGE bıraktıysa bot hiç çalışmaz.
   - `order_manager.py:14-28`, `liquidation.py:39-42`

5. **Trailing SL race — yetim reduceOnly emir** — yeni SL kuruluyor sonra eskisi cancel; iki SL aynı anda canlı kalıp ters yönlü yeni pozisyonu kısmen kapatabilir.
   - `order_manager.py:295-307`

---

## 3. Ajanlar Arası Çelişki / Tartışma

### A. Mimari ajanı vs Strateji/Trader/Backtest ajanları
- **Mimari:** "Çekirdek (`order_manager.py`, `risk.py`, `execution_guard.py`) iyi yazılmış, refactor yeterli, rewrite gerekmez."
- **Strateji + Trader + Backtest:** "Kod kalitesi alakasız — sinyal kombinasyonu istatistiksel olarak ölü, refactor edilse bile para basmaz."
- **Sentez:** Mühendislik kabuğu sağlam, içindeki strateji çürük. Yatırım önceliği refactor değil, **strateji baştan tasarımı** olmalı.

### B. Memory'deki "%4-5 yıllık" rakam
4 ajan (Backtest, Quant, Trader, Strateji) bu rakamın **bile abartı** olduğunu söyledi. Realistik medyan **~%0-3 net**, varyans yüksek.

### C. Konfig vs Dökümantasyon Çelişkisi
- `docs/RISK_OPTIMIZATION_10_AGENT.md`: "Balanced: 5x leverage, %3 risk, %3 daily limit"
- Canlı `config.py:23-30`: **10x leverage, %4 risk, %6 daily limit** (`growth_70_compound`)
- Sonuç: Kullanıcının %3.5 max DD beklentisi gerçek dışı — WF OOS DD'leri zaten %5.8-16.3 (BTC tek sembol).

---

## 4. Sayısal Gerçeklik Envelopu

| Senaryo | 12-ay net | Olasılık |
|---|---|---|
| Worst (rejim değişir + 1 black swan + funding spike) | **-%15 ile -%30** | %25 |
| Base (normal kripto yılı) | **-%3 ile +%5** | %50 |
| Best (2024 tipi trend yılı + altseason + DOGE/TRX şanslı) | **+%15 ile +%30** | %20 |
| Backtest iddiası "%79-124 CAGR" | **canlıda olmayacak** | <%5 |

- **Net pozitif olma ihtimali ~%50-55** (yazı-tura)
- **Sharpe gerçekçi: 0.2-0.5** (profesyonel para çekmez)
- **Maliyet kontrolü:** 264 trade × ~%0.23 round-trip ≈ %60-100 yıllık cost/equity. +%0.3 slippage hatası tüm "kazancı" siler.

---

## 5. Ne Yapmalı — Öncelik Sırası

### A. Live'a çıkma — ne testnet ne mainnet
Önce metodoloji onarımı.

### B. Acil (1-3 gün) — production engelleyici buglar
- `priceProtect` bool tipine çevir
- recvWindow + `adjustForTimeDifference: True`
- ccxt versiyonunu pinle
- `set_margin_mode` + `set_position_mode` setter ekle
- RAM-only state → diske persistent JSON (atomic write)
- Lock dosyasını her cycle güncelle (heartbeat ile birleştir)
- `config.py`'yi `.gitignore`'a al; `config.template.py` bırak
- Telegram/email alert: daily loss, position open fail, heartbeat stale

### C. Strateji metodolojisi (2-4 hafta)
- **Gerçek walk-forward**: train segmentinde grid optimize (DONCHIAN/VOL/SL/RSI/ADX), seçilen parametreyi OOS'ta uygula. Pencereler **non-overlapping** + purge + embargo.
- **Random sembol baseline + Bonferroni** (455 × 6 = 2730 test için α=0.05/2730).
- **Deflated Sharpe Ratio** (Lopez de Prado), **PBO** (Probability of Backtest Overfitting).
- **Realistic slippage** (orderbook depth + ATR-bağımlı, min %0.3 round-trip).
- **HOLDOUT** son 6 ay (2025-11 → 2026-04) hiç dokunulmamış olarak ayrılsın.
- `bias_audit.py`'yi çalıştır, çıktısını commit et (Wilder warmup driftini gör).
- **Stationary bootstrap** (Politis-Romano) ile optimal block size; sabit `block=5` yerine.
- **Funding rate** gerçek tarihsel diziyle yeniden modellensin.

### D. Sermaye kararı
- 1000 USDT için dürüst alternatif: **Binance USDT Earn (%4-8) + BTC DCA**. Bu botun base case'iyle aynı getiri, sıfır iş, sıfır psikoloji.
- Botla devam edilecekse: 100-200 USDT'lik "öğrenme bütçesi", 6-12 ay paper + canlı izleme.

---

## 6. Ajan Bazlı Detay Bulgular

### 1. Strateji & Sinyal Mantığı
- EMA 21/50 config'de ölü kod; aktif sinyal Donchian breakout
- Wilder smoothing'de NaN warmup leak (ilk RSI_PERIOD bar'da kirli RSI)
- 7-katmanlı filtre cascade overfit (3 yılda 86 trade, p-hacking riski yüksek)
- Pattern signal ağırlıkları (`pattern_signals.py:131-144`) tunable büyü sayıları, hiçbir kaynaktan türetilmemiş
- Codex AGENT_REVIEW_10_NOGO zaten BTC WF total test PnL = -3.89 USDT, NO-GO verdict vermiş

### 2. Risk Yönetimi
- `LIQUIDATION_GUARD_ENABLED = False` (config.py:70) — kritik
- `PROTECTIONS_ENABLED = False` (config.py:129) — kritik
- `risk_management.py` ölü ama tehlikeli formül (margin*leverage notional)
- Cross-margin liquidation formülü yanlış (isolated varsayar)
- Korelasyon-naif sizing (`risk.py:31-41`) — DOGE/LINK/TRX +0.85 korelasyona sahip
- Doc-config tutarsızlığı: balanced profile reddedilmiş, agresif `growth_70_compound` aktif

### 3. Backtest Doğrulama
- Walk-forward'da pencereler %85 örtüşüyor (`train_bars=3000, roll_bars=500` 4H'de)
- Strateji parametreleri WF train segmentinde optimize EDİLMİYOR
- Min notional filtresi (100 USDT) backtest'te survivorship yaratıyor
- Funding rate fallback `0.0001/8h` post-hoc seçilmiş, ileri yön bias
- 264 trade × %0.23 nominal cost ≈ %106 — küçük slippage hatasında kâr buharlaşır

### 4. Execution & Order Management
- `_resolve_market_fill` partial fill'i full sayıyor (yanlış!)
- `clientOrderId` set edilmiyor → idempotency yok, network timeout retry'da çift emir
- TWAP boş kabuk (sadece eşit dilim plan, hiçbir yerden çağrılmıyor)
- `trade_executor.py` ölü kod — bot.py ve paper_runner aynı mantığı duplicate ediyor
- Paper'da slippage sabit 7.5 bps, exchange filter/lot step kontrolü yok → paper-prod ayrışması
- Paper'da SL emri yok (intra-bar high/low check), prod'da MARK_PRICE; funding payment paper'da 0

### 5. Binance API & Exchange Filters
- `recvWindow` ve `adjustForTimeDifference` set edilmemiş — Windows NTP drift > 1000ms ise tüm cagrılar `-1021` reject
- `MARGIN_MODE = "cross"` ama `set_margin_mode` çağrısı YOK
- `ensure_one_way_mode` sadece okuyor, set etmiyor — kullanıcı HEDGE bıraktıysa bot çalışmaz
- `priceProtect = "TRUE"` string (bool olmalı)
- `round(x, 2)` SL fiyatı (execution_guard.py:31-33) — DOGE tickSize 0.00001'e iner, 2 basamak yetmez
- ccxt unpinned (`>=4.2.0`) — supply chain riski + implicit method rename riski (`fapiPrivateGetPositionSideDual`)
- Exchange filter cache invalidation yok (`exchange_filters.py:34-38`)
- WS user-data stream yok, sadece 1h polling — SL tetiklendi 1 saat boyunca state recover edilmez

### 6. Yazılım Mimarisi & Kod Kalitesi
- 40+ top-level Python dosyası (accretion pattern)
- `risk.py` + `risk_management.py` (ölü duplicate)
- `multi_symbol_backtest.py` ile `portfolio_backtest.py` örtüşüyor
- `config.SYMBOL` runtime mutation (global state) — test edilmesi imkansız, thread-safe değil
- 224 adet `getattr(config, ...)` — configuration sprawl
- 215-satırlık config.py'da 60+ feature flag (`PROTECTIONS_ENABLED=False`, `EXIT_LADDER_ENABLED=False`, `PAIR_UNIVERSE_ENABLED=False`, `TWAP_ENABLED=False`)
- Ham CSV dosyaları repo kökünde (568KB equity, 507KB monte_carlo) — kod ile artefakt karışık
- **Teknik borç skoru: 7/10** — refactor yeterli, rewrite gerekmez

### 7. State Management & Crash Recovery
- Live `bot.py` state'i tamamen RAM'de — diske yazılmıyor
- `_recover_position` borsada SL yoksa **soft tahmin** yapıyor ama yeni SL **borsaya yerleştirmiyor** → orphan SL durumunda pozisyon "korumalı" sanılır, oysa çıplak
- Lock dosyası heartbeat'le güncellenmiyor — manuel restart 4 saat bloklanabilir
- `clientOrderId` yok → idempotency TOCTOU açığı
- `df.iloc[-2]` 2 saat down sonrası stale signal execution riski
- **Crash recovery olgunluğu: 3/10**

### 8. Quant / İstatistik
- Win-rate 95% CI: 244 trade'de [76.7%, 86.4%] — sadece 1 sigma kanıt
- 7 fold WF, fold başına 13-27 trade — sample yetersiz
- Sharpe / Sortino / annualization YOK
- Multiple testing: 455 × 6 = 2730 test, Bonferroni yok (α=0.05/2730 = 1.8e-5 gerekli)
- Monte Carlo bootstrap IID ihlali — `loss_probability=0.0%` fiziksel imkânsızlık
- `dd_max_pct=89.8%` (bootstrap) — ruin scenario %0.72 ama "growth" doc'unda overlooked
- Underwater duration HİÇ ölçülmemiş
- BTC tek sembol WF degradation: train +5773 → test +43 USDT (~%99 degradation)

### 9. Ops / Güvenlik
- `config.py` git'te + runtime config — secret leak riski
- `.env` dosyası yok, sadece env var
- `LIVE_TRADING_APPROVED` tek-değişken zayıf (CLI flag/hardware token yok)
- Permission scope/IP whitelist hiçbir doc'ta belirtilmemiş — Withdraw açıksa key sızıntısında para gider
- Telegram/email/SMS/webhook bildirim YOK
- Heartbeat var ama monitor edilmiyor (cron/scheduler yok)
- Prometheus/StatsD/dashboard YOK
- Audit trail sadece paper modda; live `bot.py`'de "neden bu trade" snapshot YOK
- Kill switch tek-komut yok
- requirements pinning yok, `pip-audit`/`safety` izi yok
- **Production-ready skoru: 3/10**

### 10. Trader Perspektifi
- Strateji 30+ yıldır crowded (Donchian Turtles)
- Backtest sayıları üç kez aşağı düzeltildi: %100 → %33 → %4-5; her seferinde **aşağı revize**
- Sample size 57 → 86 → 244 hâlâ zayıf, win rate %66-83 arası salınıyor (gerçek edge'in WR'ı bu kadar oynamaz)
- Donchian breakout level'ı zaten herkesin gördüğü → likidite av yemi (stop hunt)
- 10x leverage + %4 risk × max 2 pos: 3 ardışık stop = -%30 equity
- Black swan'da `stop_market` exchange halt'ında çalışmaz
- **"Bu botu kendi paramla çalıştırır mıyım?" Hayır.** En fazla 200 USDT acı kesesi + paper.
- Alternatif: USDT Earn (%4-8) sıfır risk, BTC DCA, funding rate arbitrage — hepsi risk-adjusted bazda **bot'tan üstün**

---

## 7. Önemli Doğrulama Testleri (canlı para öncesi)

1. **Filtre ablation**: her filtre tek tek kapatılarak WR/PF/sample ölç
2. **Pattern signals permutation test**: 1000 kez shuffle → null dağılımdaki p-değer
3. **Wilder warmup unit test**: TA-Lib ile karşılaştır, ±0.5 puan sapma kabul
4. **Out-of-sample tarihsel pencere**: 2019-2022 BTC verisinde tek değişiklik yapmadan koş
5. **In-sample/OOS Sharpe oranı**: < 0.4 ise edge istatistiksel değil
6. **Random sembol baseline + Bonferroni**
7. **Path-dependent Monte Carlo**: bootstrap %return değil, signal listesi gerçek equity üzerine
8. **Realistic slippage modeli** (Almgren-Chriss)
9. **Out-of-sample HOLDOUT** son 6 ay
10. **Stress test:** 2022 LUNA, 2020-03-12, 2024-08-05 senaryoları izole
11. **Funding rate stress**: 2021-04, 2022-05, 2023-03 spike pencereleri
12. **Costs sensitivity:** slippage 5→25 bps, commission 8→12 bps → CAGR negatif mi?
13. **Live testnet 200+ trade** (mevcut 30-50 hedef yetersiz)

---

## 8. Sonuç

Kod tabanı mühendislik açısından kurtarılabilir (refactor + test backfill 2-3 hafta), ancak **sinyal seti BTC/altcoin 4H'de istatistiksel olarak para basmıyor**. Mevcut "%79 CAGR growth_70_compound" iddiası savunulamaz. Live deployment için temel değil. Üç yol var:

1. **Bırak**: 1000 USDT'yi USDT Earn'e koy, sıfır iş, %4-8/yıl
2. **Öğren**: 100-200 USDT acı kesesi, paper + testnet 6-12 ay, **strateji baştan tasarımı**
3. **Devam**: bu repo ile canlıya çıkmak — beklenen değer 0 ± çok geniş bant; net negatif risk-adjusted

Tavsiye: **Yol 1 veya Yol 2.** Yol 3 fiziksel olarak imkânsız değil ama beklenen değer alternatife karşı negatif.

---

*Rapor hazırlanışı: 10 paralel uzman ajan (Claude general-purpose alt-agent), read-only mod, ~2026-05-01.*
*Kapsam dışı (Codex aktif): `order_manager.py`, `tests/test_safety.py`, `walk_forward_results.csv`, `exchange_filters.py` — bu dosyalar okundu ama yazılmadı.*
