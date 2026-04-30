# Notional Bug Fix — Etki Raporu

**Tarih:** 2026-04-30
**Bulan:** 5 ajan denetim turu (Ajan 1 — Funding Cost Modeling)
**Düzeltme:** `backtest.py:127`

---

## Bug

```python
# YANLIŞ (çift sayım)
notional = (entry + exit_price) * size

# DOĞRU (ortalama × büyüklük)
notional = (entry + exit_price) / 2 * size
```

`(entry + exit_price)` zaten iki fiyatın **toplamı**. Ortalama nominal için 2'ye bölünmesi gerekiyor. Bug nedeniyle:
- Komisyon (%0.08) **2× düşülüyordu**
- Slippage (%0.15) **2× düşülüyordu**
- Funding (signed) **2× düşülüyordu**

Bu, gerçek getiriyi sistematik olarak baskılıyordu.

---

## Etki — Düz Backtest (3 yıl)

| Sembol | Önce (bug'lı) | Sonra (fix) | Δ |
|---|---:|---:|---:|
| BTC/USDT | +76.03 | **+249.88** | +173.85 (+229%) |
| ETH/USDT | +243.94 | **+369.30** | +125.36 (+51%) |
| SOL/USDT | +473.80 | **+601.86** | +128.06 (+27%) |
| BNB/USDT | +79.11 | **+207.43** | +128.32 (+162%) |
| **Ortalama** | +218 | **+357** | +%64 |

Win rate'ler de yukarı çıktı:
- BTC: %55.8 → **%66.3**
- ETH: %63.6 → **%76.6**
- SOL: %72.2 → **%78.9**
- BNB: %57.1 → **%72.9**

**Yorum:** Gider 2× şiştiği için kazanan trade'ler bile zarar gözüküyordu. Fix sonrası gerçek tablo ortaya çıktı.

---

## Etki — Walk-Forward (BTC, 7 dönem)

| | Önce | Sonra |
|---|---:|---:|
| Pozitif dönem | 3/7 | **4/7** |
| Test ortalama | -13.2$ | **-0.6$** |
| Train ortalama | +192 | +292 |
| Train>Test farkı | +205 | +293 |

BTC walk-forward break-even'a yakınlaştı ama hala marjinal.

---

## Etki — Multi-Symbol Walk-Forward (4 sembol × 7 dönem)

| Sembol | Önce | Sonra |
|---|---|---|
| BTC | 3/7 pozitif, ort -13$ | **4/7**, ort **-0.6$** |
| ETH | 4/7 pozitif, ort +5$ | **5/7**, ort **+17$** |
| SOL | 5/7 pozitif, ort +14$ | **6/7**, ort **+29$** |
| BNB | 4/7 pozitif, ort +7$ | **6/7**, ort **+40$** |

**Toplam test pencere:**
- Önce: 16/28 pozitif (%57)
- Sonra: **21/28 pozitif (%75)** ← belirgin iyileşme

**Test ortalaması (sembol arası):** +2.3$ → **+21.4$** (10× artış)

---

## Etki — Monte Carlo (BTC)

| | Önce | Sonra |
|---|---:|---:|
| Tarihsel DD | 54$ | 54$ |
| MC DD medyan | 98$ | **78$** |
| MC DD p95 | 161$ | **129$** |
| MC DD max | 225$ | **199$** |
| MC PnL (sabit) | 76$ | **250$** |

DD p95 161 → 129 (sermayenin %16'sından %13'e düştü).

---

## Yeni Verdikt

### 4/4 Sembolde Pozitif
- Düz backtest: 4/4 pozitif (önceden de öyleydi ama PnL çok daha yüksek)
- Walk-forward: 3/4 sembolde test ortalaması pozitif (BTC marjinal)
- Toplam test pencerelerinin %75'i pozitif

### Hala Şart Olanlar
1. **Block-bootstrap MC** — IID varsayım ihlali
2. **Çoklu sembol Monte Carlo** — sadece BTC'de yapıldı
3. **Parametre stabilite haritası** — yakın parametreler de iyi çalışıyor mu?
4. **Production altyapı** — Telegram, retry, state desync (Ajan 5)
5. **Testnet 2 ay paper trading**

### Canlı Karar

Strateji "umut verici hipotez" → **"sağlam aday"** seviyesine yükseldi:
- 4 sembolde pozitif PnL
- 21/28 walk-forward dönemi karlı
- DD p95 sermayenin %13'ü (kabul edilebilir)

Ama **henüz canlı para değil**. Sıradaki kapı testnet/paper trading.

---

## Reproducibility

```bash
git checkout 5a53f30^      # bug öncesi commit
python backtest.py          # eski sayılar
git checkout main
python backtest.py          # yeni sayılar (fix uygulanmış)
```

Tüm sonuçlar `*_results.csv` dosyalarında.
