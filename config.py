import os

# --- API ---
API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TESTNET    = True   # False = canlı işlem

# --- Piyasa ---
SYMBOL          = "BTC/USDT"
TIMEFRAME       = "4h"
DAILY_TIMEFRAME = "1d"          # Yüksek TF trend filtresi
LEVERAGE        = 3

# --- Sermaye & Risk ---
CAPITAL_USDT         = 1000.0
RISK_PER_TRADE_PCT   = 0.02     # %2 per trade
MAX_OPEN_POSITIONS   = 2
DAILY_LOSS_LIMIT_PCT = 0.03     # %3 günlük kayıp → bot durur

# --- SL / TP (ATR çarpanı) ---
SL_ATR_MULT = 2.0
TP_ATR_MULT = 4.0

# --- Trend takip indikatörleri (eski mantık, bazı yardımcılar hala kullanılıyor) ---
EMA_FAST   = 21
EMA_SLOW   = 50
ADX_PERIOD = 14
ADX_THRESH = 20
RSI_PERIOD = 14
ATR_PERIOD = 14

# --- Donchian breakout (ana sinyal) ---
DONCHIAN_PERIOD = 20            # 4H mum sayısı (~3.3 gün)
DONCHIAN_EXIT   = 10            # Erken çıkış için daha sıkı kanal

# --- Hacim filtresi ---
VOLUME_MA_PERIOD = 20
VOLUME_MULT      = 1.5          # Kırılım barı hacmi >= 1.5 × ortalama

# --- 1D trend filtresi ---
DAILY_EMA_PERIOD = 50           # Günlük EMA50 — fiyat üstü ise long-only

# --- RSI aşırı bölge filtresi (kırılım sırasında pump/dump'ı engelle) ---
RSI_MAX_LONG  = 75              # Long sinyali için RSI <= 75
RSI_MIN_SHORT = 25              # Short sinyali için RSI >= 25

# --- Veri ---
WARMUP_BARS = 250               # 4H mum (Donchian + EMA50 + ATR ısınması)
