import os

# --- API ---
API_KEY    = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")
TESTNET    = True   # False = canlı işlem

# --- Piyasa ---
SYMBOL     = "BTC/USDT"
TIMEFRAME  = "4h"
LEVERAGE   = 3

# --- Sermaye & Risk ---
CAPITAL_USDT        = 1000.0
RISK_PER_TRADE_PCT  = 0.02    # %2 per trade
MAX_OPEN_POSITIONS  = 2
DAILY_LOSS_LIMIT_PCT = 0.03   # %3 günlük kayıp → bot durur

# --- SL / TP (ATR çarpanı) ---
SL_ATR_MULT = 2.0
TP_ATR_MULT = 4.0   # 1:2 risk/ödül

# --- İndikatör parametreleri ---
EMA_FAST   = 21
EMA_SLOW   = 50
ADX_PERIOD = 14
ADX_THRESH = 20
RSI_PERIOD = 14
RSI_LONG_MIN  = 40
RSI_LONG_MAX  = 70
RSI_SHORT_MIN = 30
RSI_SHORT_MAX = 60
ATR_PERIOD = 14

# --- Veri ---
WARMUP_BARS = 200   # indikatör ısınması için gerekli mum sayısı
