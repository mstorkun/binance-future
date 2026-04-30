# Binance Futures Trading Bot

BTC/USDT 4H trend takip botu. EMA 21/50 + ADX + RSI + ATR sinyali, ATR tabanlı stop-loss, trailing stop ve trend tersine dönüş çıkışı ile.

> **Durum:** Geliştirme aşamasında. Walk-forward analiz overfitting gösterdi, canlı kullanılmamalı. Detay: [docs/WALK_FORWARD.md](docs/WALK_FORWARD.md).

## Hızlı Bakış

| | |
|---|---|
| **Sermaye** | 1000 USDT |
| **Sembol** | BTC/USDT Perpetual |
| **Zaman dilimi** | 4 saat |
| **Kaldıraç** | 3x |
| **Per trade risk** | %2 (20 USDT) |
| **Max drawdown limiti** | %3 günlük |

## Strateji

Trend takip — sinyal koşulları:

1. EMA 21/50 kesişimi (trend dönüşü)
2. ADX > 20 (trend gücü)
3. RSI 40-70 (long) veya 30-60 (short) — aşırı bölge dışı

Çıkış:
- ATR tabanlı initial stop-loss (1.5×ATR)
- Trailing stop: kazancın %15'ini geri ver, %85'ini kilitle
- Trend tersine dönerse market kapatma

## Dosya Yapısı

```
binance-bot/
├── config.py           # Tüm parametreler
├── data.py             # ccxt veri çekme
├── indicators.py       # EMA, ADX (Wilder), RSI (Wilder), ATR (Wilder)
├── strategy.py         # Sinyal mantığı
├── risk.py             # Pozisyon boyutu, SL/TP
├── order_manager.py    # Emir yönetimi (atomik açma + rollback)
├── bot.py              # Canlı bot ana döngüsü
├── backtest.py         # Vektörel backtest
├── optimize.py         # Parametre tarama
├── walk_forward.py     # Out-of-sample doğrulama
├── requirements.txt
├── .env.example
└── docs/               # Denetim raporları, sonuçlar
    ├── REVIEW.md          # 5 ajan denetim raporu
    ├── BUGS_FIXED.md      # Düzeltilen 12 kritik bug
    ├── BACKTEST_RESULTS.md
    ├── WALK_FORWARD.md
    ├── ARCHITECTURE.md
    └── NEXT_STEPS.md
```

## Kurulum

```bash
pip install -r requirements.txt
cp .env.example .env
# .env dosyasına API key/secret yaz
python backtest.py        # Geçmiş veride test
python walk_forward.py    # Overfitting kontrolü
python bot.py             # Canlı çalıştır (sadece testnet öneriliyor)
```

## Diğer AI'lar İçin Notlar

Bu repo bir başka AI/mühendis tarafından review edilebilir. Şuradan başlayın:

1. [docs/REVIEW.md](docs/REVIEW.md) — Önceki review bulguları
2. [docs/BUGS_FIXED.md](docs/BUGS_FIXED.md) — Düzeltilen bug'lar
3. [docs/WALK_FORWARD.md](docs/WALK_FORWARD.md) — Stratejinin neden çalışmadığı
4. [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) — Önerilen iyileştirme yolları

## Lisans

Kişisel kullanım — paylaşmadan önce sorulması gerekir.
