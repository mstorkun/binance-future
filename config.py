import os

# --- API ---
API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TESTNET    = True   # False = canlı işlem

# --- Piyasa ---
SYMBOLS         = ["SOL/USDT", "ETH/USDT", "BNB/USDT"]
SYMBOL          = "BTC/USDT"
TIMEFRAME       = "4h"
DAILY_TIMEFRAME = "1d"          # Yüksek TF trend filtresi
LEVERAGE        = 5             # Balanced profile selected by risk sweep

# --- Sermaye & Risk ---
CAPITAL_USDT         = 1000.0
RISK_PER_TRADE_PCT   = 0.03     # %3 per symbol sleeve; ~%1 portfolio risk on first trade
MAX_OPEN_POSITIONS   = 2
DAILY_LOSS_LIMIT_PCT = 0.03     # %3 daily loss -> bot stops
DYNAMIC_RISK_ENABLED = True
DYNAMIC_RISK_MIN_MULT = 0.50
DYNAMIC_RISK_MAX_MULT = 1.25
FINAL_RISK_MIN_MULT = 0.10
FINAL_RISK_MAX_MULT = 1.25
CALENDAR_RISK_ENABLED = True
CALENDAR_EVENT_FILE = "event_calendar.csv"
WEEKEND_RISK_MULT = 0.70
WEEKLY_OPEN_RISK_MULT = 0.75
FUNDING_RISK_MULT = 0.90
FUNDING_WINDOW_MINUTES = 30
DAILY_CLOSE_RISK_MULT = 0.85
DAILY_CLOSE_WINDOW_MINUTES = 60

# --- SL / TP (ATR çarpanı) ---
SL_ATR_MULT = 2.0
TP_ATR_MULT = 4.0

# --- Backtest maliyet varsayımları ---
# Tarihsel funding verisi çekilemezse fallback olarak kullanılır.
DEFAULT_FUNDING_RATE_PER_8H = 0.0001

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
