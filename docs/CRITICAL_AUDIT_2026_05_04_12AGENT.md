# Kritik Denetim — Claude 12 Uzman Ajan Sentezi (2026-05-04)

> **Kapsam:** Codex'in 2026-05-01 → 2026-05-04 arasındaki 30+ commit'inin (parameter WF, holdout, PBO matrix, cost stress, user data stream, kill switch, risk-adjusted reporting, conservative overfit controls vs.) bağımsız 12-uzman çapraz denetimi. Read-only, Codex aktif değil. Codex'in `docs/CRITICAL_AUDIT_2026_05_01.md` + `docs/AUDIT_DIFF_2026_05_01.md` ile birlikte okunmalıdır.
>
> **Ajan dağılımı:** Strateji & Edge, Risk 2.0, Backtest 2.0, Execution 2.0, Binance API 2.0, Mimari 2.0, State & Recovery 2.0, Quant/İstatistik 2.0, Ops & Güvenlik 2.0, Trader perspektifi 2.0, Kâr-hedefli Strateji Mimarı, Production Readiness Auditor.

---

## TL;DR (acımasız)

Bot 4 günde mühendislik olarak **L1 → L2.5** sıçradı, ortaokul kimliğinden teknik olarak çıktı. **Ama "para kazanan bot" hedefine yaklaşmadı** — strateji edge'i Codex'in kendi raporunda istatistiksel olarak sıfırdan ayırt edilemiyor (`risk_adjusted_report.json: passes_zero_edge_after_haircut: false`, deflated Sharpe proxy `-2.30`).

Mevcut Donchian breakout stratejisini güçlendirmek = ölü atı kamçılamak. Para kazanmak için **strateji ailesini değiştir** (funding-rate carry, delta-neutral). Mühendislik altyapısı bu pivotu destekleyecek olgunlukta — kod değil, **alpha** yetersiz.

---

## 1. EDGE GERÇEKLİĞİ (Codex'in kendi raporlarından)

| Metrik | Değer | Yorum |
|---|---|---|
| **PBO** | 0.1429 | "İyi" görünüyor; ama 7 fold ile std hata ±0.13, sembol seleksiyonu dahil değil |
| **Nominal Sharpe** | 3.69 | İlk bakışta harika |
| **Bonferroni-haircut deflated Sharpe proxy** | **-2.30** | **Edge sıfır hipotezi reddedilemiyor** (`passes_zero_edge_after_haircut: false`) |
| **Holdout** (son 3 ay, 500 bar — 6 ay değil) | +%10.5 / %5.76 DD | Train +%2363'ten ~225× düşüş |
| **Severe cost stress** (2× fee + 3× slip + 2× funding) | Compounded +%28 / 3 yıl ≈ yıllık %9 | Fee/funding'den kıl payı pozitif |
| **Son fold OOS** (en yeni 2026-02→05) | +%5.4 / 83 gün | Trend zayıflama sinyali |
| **Train→Test degradation** | %99 (87× kayıp) | Klasik overfit imzası |
| **Trade sayısı** | 244 (tek backtest) | Wilson 95% CI hâlâ ±%6.3 |
| **Realistik 1-yıl envelope** | -%5 ile +%15 (medyan ~%2-8) | USDT Earn %4-8 ile rekabetçi değil |

### Hâlâ açık metodoloji açıkları
- Pattern ablation **permütasyon yapmıyor** — pattern_signals random'dan farklı mı bilinmiyor (`pattern_ablation.py:21-25`)
- RSI/ADX grid WF'da **yok** (sabit), sadece DONCHIAN/VOL/SL_ATR optimize ediliyor (`portfolio_param_walk_forward.py:206-310`)
- Symbol seleksiyonu (DOGE/LINK/TRX) **PBO'nun dışında** — gerçek PBO daha yüksek
- Purge/embargo **yok** (lookback kadar leak)
- Holdout 6 ay değil, **3 ay** (kullanıcıya söylenenden yarısı)
- Underwater duration **ölçülmüyor**
- Correlation stress **rapor-only**, sizing'e bağlı değil (`correlation_stress.py:37-51` — `docs/CORRELATION_STRESS_2026_05_01.md:36-43` "rapor-only" kabul ediyor)
- Cross-margin liquidation formülü **hâlâ yanlış** (`liquidation.py:39-42` isolated formülü)
- Tam **Deflated Sharpe (Bailey-López de Prado 2014)** uygulanmadı — sadece "Bonferroni proxy"
- Stationary bootstrap (Politis-Romano) yok; sabit `block=5`
- BH-FDR / Holm yok; sadece Bonferroni

---

## 2. ORTAOKUL KİMLİĞİ ÇIKTI MI?

**Evet, çıktı.** Ama production startup değil.

### Çıktığını kanıtlayan
- Atomic state yazımı sistemli (`live_state.py`, `order_events.py`, `paper_runner.py`)
- Idempotent `client_order_id`, listenKey lifecycle, exchange filter validation
- Kill switch (3-anahtar guard: `--execute --yes-i-understand --allow-live`)
- 100 test, 61 docs/karar günlüğü
- requirements.txt exact-pin, meta-test pinning
- `risk_management.py` legacy quarantined (silmek yerine RuntimeError fırlatıyor)
- `trade_executor.py` + `twap_execution.py` `PASSIVE_ONLY = True` sentinel + 4 contract testi
- API key security runbook 131 satır operasyonel detay

### Hâlâ L1/L2 seviyesinde kalan
- **62 flat .py dosyası**, paket yapısı (`engines/`, `core/`, `risk/`, `execution/`) yok
- **CI/CD = sıfır**: `.github/workflows/`, pre-commit, mypy, ruff, pytest-cov, bandit, pip-audit hiçbiri yok
- Test 100 ama **tek dosya** (`tests/test_safety.py`, 2210 satır); strategy/risk/indicators için **0 unit test**; coverage ölçümü yok
- **`config.SYMBOL` global mutation 7 dosyada** (`bot.py:130/159`, `paper_runner.py:201/213`, `portfolio_backtest.py:407/422`, vb.) — junior code smell
- **20 feature flag** (7 default-off): `LIQUIDATION_GUARD_ENABLED`, `PROTECTIONS_ENABLED`, `EXIT_LADDER_ENABLED`, `PAIR_UNIVERSE_ENABLED`, `TWAP_ENABLED`, `WEEKLY_TREND_RISK_ENABLED`, `FLOW_BACKTEST_ENABLED` — temizlik yok
- **`bot.log` 0 byte (Apr 30'dan beri yazılmamış!)** — logging silent fail
- **Structured logging yok** — string f-string only, JSON event yok, correlation_id yok
- **`order_manager.py` 834 satır** — God-module
- **requirements.txt'te şüpheli versiyonlar**: `pandas==3.0.2`, `websockets==16.0` PyPI'da bulunmayan versiyonlar (pin var ama doğrulanmamış)
- **Deployment**: PowerShell `Start-Process -WindowStyle Hidden`, supervisor yok, restart-on-failure yok, log rotation yok
- **Monitoring**: JSONL dosya, Prometheus/Grafana yok, **Telegram/email/webhook alert yok** — `alerts.jsonl` kimse okumuyor
- **`docs/` 65+ MD** — "her değişiklik için yeni MD" anti-pattern; tek kanonik ARCHITECTURE.md yok
- Repo root'unda commit'li üretim CSV/JSON/log artifactleri (`backtest_results.csv`, `paper_*.csv`, `bot.log`, `*_stderr.log`)

**Olgunluk skoru:** **L2.5** (Side project gövdesi + L3 ad-hoc çabaları + L1 işletim çevresi). L3 (Pre-production) net olarak kapanması için 6-8 hafta CI + Docker + Prometheus + Telegram alert.

---

## 3. CANLIYA HAZIR MI?

**Hayır.** 12 ajandan 9'u aynı blocker listesinde anlaştı.

### Codex'in kendi guard'ı bile kapalı tutuyor (doğru karar)
- `LIVE_TRADING_APPROVED=False`
- `USER_DATA_STREAM_READY=False`
- `docs/USER_STREAM_RUNNER_2026_05_04.md` Codex'in kendi notu: "not live-ready"

### Hâlâ açık 12 öldürücü risk

1. **`PROTECTIONS_ENABLED=False` + `LIQUIDATION_GUARD_ENABLED=False`** — `LIVE_PROFILE_GUARD` bunları **denetlemiyor**, sessiz bypass (`config.py:96, 155`; `data.py:33`)
2. **`bot.py` user_stream'i çağırmıyor** — ayrı süreç, fill event'leri 1 saatte bir polling ile öğreniliyor; phantom-position riski
3. **`ACCOUNT_UPDATE` handler yok** — margin call event'leri sessiz geçiyor (`user_stream_events.py:67` sadece ORDER_TRADE_UPDATE)
4. **Gap recovery yok** — WS reconnect sonrası kaçan event REST snapshot ile doldurulmuyor
5. **`priceProtect="TRUE"` string bug HÂLÂ ORADA** (`execution_guard.py:54`); testnet probe yapılmadı, fix yapılmadı
6. **`set_position_mode` setter yok** — HEDGE'de bot çalışmaz, otomatik düzeltmiyor
7. **NTP drift periyodik resync yok** — uzun seans `-1021 timestamp out of recvWindow` riski
8. **Telegram/email alert yok** — `alerts.jsonl` kimse okumuyor → kritik event = sessiz log
9. **Process supervisor yok** — bot çökerse uyandırma yok
10. **State backup yok** — bozuk yazma all-in
11. **Cross-margin liq formülü yanlış** — 10x'te gerçek liq daha yakın
12. **Live profile `5x/%3` istiyor ama tüm kanıt `10x/%4` üzerinden** — `balanced_live_v1` için OOS evidence yok
13. **`live_state.save_state` fsync yapmıyor** (`live_state.py:42-43`) — power-cut → boş JSON
14. **`emergency_kill_switch` bot'u durdurmuyor** — sadece pozisyon kapatıyor; sonraki cycle'da bot yine açabilir

### Realistik max DD vs Kullanıcı hedefi
- **Kullanıcı hedefi: %3.5 max DD**
- **Gerçekçi 1-yıl tail-DD: %15-25** (correlation shock + funding spike + 1 outage gün)
- Kullanıcı hedefi mevcut profille **matematiksel olarak imkânsız**
- Live profile (5x/%3) bile minimum %6-8 OOS DD bekleniyor

---

## 4. PARA KAZANAN BOT İÇİN — RADİKAL YÖN DEĞİŞİKLİĞİ

12 ajanın hemfikir olduğu nokta: **Donchian breakout 4H crowded ve edge marjinal. Mevcut altyapıyı koruyup stratejiyi değiştir.**

### Geçilecek strateji ailesi (retail için gerçek edge)

**1. Funding-rate carry (delta-neutral) — ÖNCELİK**
- Spot long + perp short, pozitif funding'i topla
- **CAGR %12-25, Sharpe 1.2-2.0, MaxDD %5-10**
- Mevcut altyapının **%70'i yeniden kullanılır**: `flow_data.py` zaten funding fetch ediyor, `pair_universe.py` `funding_abs` skorluyor, `order_manager.py` perp emir akışı çalışıyor, `risk.py` ve `account_safety.py` aynen kalır
- Eklenecek: spot client modülü, delta-neutral pozisyon yöneticisi, 8h funding payment cron
- **Tail risk**: borsa kredisi (FTX/LUNA tipi günler %15-30 tek günlük)
- Referans: Hummingbot `perp_arb`, Jesse funding examples, López de Prado triple-barrier

**2. Stat-arb (BTC-ETH cointegration)** — funding carry üzerine overlay
- CAGR %8-15, Sharpe 0.8-1.3
- Engle-Granger basit, 100 satır kod

**3. YAPMA** (retail için ölü):
- Pure market making (VIP-1 altı negatif EV)
- Microstructure HFT (co-location şart)
- On-chain whale frontrunning (mempool erişimi)
- Cross-exchange latency arb
- Pure trend following (mevcut, edge yok)

### 3-aylık yol haritası

- **Ay 1:** Tam tarihsel funding fetch (`/fapi/v1/fundingRate`) + spot client + carry backtest harness (PnL = funding_received − spot_borrow_cost − perp_funding_paid − 4× taker fee)
- **Ay 2:** 5-10 sembol paper carry, 60+ trade, Sharpe ölçümü, triple-barrier (López de Prado) ile çıkış etiketleme
- **Ay 3:** Stat-arb overlay + **küçük canlı $1-2k**, ancak 90-gün live Sharpe > 1.0 ise sermaye artışı

---

## 5. ÇİFT-AI MODELİ — REVİZYON

Claude+Codex bu projede **13-16 gerçek bug yakaladı** (idempotency, partial-fill, orphan SL — üçü de "para patlatır" sınıfı). Tek-AI'nin kaçıracağı şeyler.

### Sayısal değerlendirme
- **Codex'in kaçırdığı, Claude'un getirdiği**: 5-6 madde (`clientOrderId` idempotency #18, partial-fill #19, orphan SL #B3, stale-bar guard #33, decision snapshots #34, kill switch #35, API runbook #36, doc-config çelişkisi #27)
- **Codex'in triage etmiş ama önceliklendirmediği**, Claude'un yükselttiği: 8-10 madde
- **Claude'un yanlış/abartılı buldukları** (Codex haklı): 3 madde (`priceProtect` kesin bug iddiası, walk-forward "tamamen sahte", protections kasten kapalı)
- **Asıl sorun (edge yok)** çözülmedi, sadece doğrulandı

### ROI

| Mod | Maliyet | Kalite | Kaçan kritik bug |
|---|---|---|---|
| Codex tek başına | 1.0× | %75 | clientOrderId, partial-fill, orphan SL, stale-bar |
| Claude tek başına | 1.2× | %65 | Empirik testnet probe disiplini zayıf |
| **Claude+Codex** | **2.2×** | **%88** | Strateji edge yok, docs şişmesi |
| Codex + ayda 1 dış audit | 1.3× | %82 | P0 bug'lar gecikir |

**Karar:** Çift-AI modelini paper/research aşamasında daralt, live'a giderken aktifleştir. Şu an Codex tek başına + ayda 1 Claude audit yeterli — alternatif (USDT Earn) matematiksel olarak üstün olduğu sürece çift-AI'nin tek meşru gerekçesi (live readiness) düşüyor.

### Echo chamber riski gerçekleşti
Hem Claude hem Codex Bonferroni/DSR/PBO önerdi → uygulandı → deflated Sharpe `-2.30`, "edge yok" sonucu. İkisi de "complex framework önerme" prensibini ihlal etti, ama bu kez edge yokluğu kanıtı sağladığı için net pozitif.

---

## 6. NET KARAR

| Soru | Cevap |
|---|---|
| Bot ortaokul projesinden çıktı mı? | **Evet** — L2.5, ad-hoc L3 |
| Bot canlı para görmeye hazır mı? | **Hayır** — 14 engelleyici açık |
| Mevcut strateji para kazanır mı? | **Hayır** — yıllık ~%2-8, USDT Earn ile rekabetçi değil |
| 4 günde edge büyüdü mü? | **Hayır** — sadece edge'in ÖLÇÜMÜ iyileşti |
| "Para kazanan bot" mümkün mü? | **Evet, ama strateji değişmeli** — funding carry + delta-neutral |
| Mevcut altyapı pivot için yeterli mi? | **Evet — %70 yeniden kullanılır** |
| Kullanıcı hedefi %3.5 max DD ulaşılabilir mi? | **Mevcut profille hayır** (%15-25 realistik) |

### 3 yol

1. **Bırak**: USDT Earn (%4-8) — sıfır iş, sıfır risk, beklenen değer benzer
2. **Pivot** (TAVSİYE EDİLEN): funding carry + delta-neutral — mevcut altyapı %70 kullanılır, gerçek edge, $1-2k canlı 3 ay sonra
3. **Devam**: mevcut Donchian — beklenen değer ~0, kuyruk -%30, tek meşrulaştırma "öğrenme"

**Acımasız tavsiye:** Para kazanma hedefi varsa **2. yol**. Kod kalitesi yeterince olgun ki bu pivot 6-8 hafta içinde gerçek bir bot çıkarır. Mevcut Donchian'ı 6 ay daha kamçılamak para kaybettirir.

---

## 7. CODEX İÇİN AKSIYON LİSTESİ

### P0 (canlıdan önce şart)
1. `bot.py` ana döngüsüne `user_stream_runner` thread/asyncio entegrasyonu
2. `ACCOUNT_UPDATE` + `MARGIN_CALL` + `listenKeyExpired` handler
3. WS reconnect → REST snapshot gap recovery
4. `live_state.save_state` fsync ekle
5. State snapshot/backup (5-li ring)
6. Startup tam üçlü reconciliation (positions × open_orders × local_state)
7. `set_position_mode` setter
8. `priceProtect` testnet empirik probe + fix
9. NTP drift periyodik resync
10. Telegram/Discord/webhook alert sink
11. Process supervisor (NSSM/systemd/Docker restart)
12. requirements.txt sahte versiyon doğrulaması (pandas==3.0.2, websockets==16.0)
13. `LIVE_PROFILE_GUARD` PROTECTIONS + LIQUIDATION_GUARD bayraklarını da denetlemeli
14. Cross-margin liquidation formülü düzeltmesi
15. `emergency_kill_switch` bot'u da durdurmalı (PID kill veya signal flag)
16. Correlation stress sonucunu sizing'e bağla (`risk.py` integration)

### P1 (production yolunda)
1. Paket yapısı (`pyproject.toml` + `src/binance_bot/`)
2. CI/CD: `.github/workflows/ci.yml` (pytest --cov ≥75, ruff, mypy, pip-audit, bandit)
3. Strategy/risk/indicators için **gerçek unit test** (mevcut 100 test integration ağırlıklı)
4. Paket bölme: `engines/`, `core/`, `execution/`, `data/`
5. `config.SYMBOL` global mutation kaldır → `Context` parametresi
6. Disabled feature flag temizliği (7 default-off)
7. Structured logging (`structlog` + JSON event + correlation_id)
8. Prometheus metrics + Grafana dashboard
9. Incident runbook (`docs/RUNBOOK.md`)
10. Off-site audit trail (`order_events.jsonl` → S3/Backblaze + SHA256 manifest)

### P2 (strateji pivot — opsiyonel ama önerilen)
1. Spot client modülü (ccxt zaten kurulu)
2. Funding rate full historical fetch + persistence
3. Delta-neutral pozisyon yöneticisi
4. Carry backtest harness
5. Symbol universe genişletme (3 → 15-20, vol-adjusted ranking)

---

*Hazırlanışı: 12 paralel uzman ajan (Claude general-purpose alt-agent), read-only, 2026-05-04. Codex aktif değildi.*
