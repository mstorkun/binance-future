# API Ayarları (Burası testnet veya gerçek API key'lerinizle doldurulmalı)
API_KEY = "BURAYA_API_KEY_GELECEK"
API_SECRET = "BURAYA_SECRET_KEY_GELECEK"

# Bot Ayarları
SYMBOL = "BTC/USDT:USDT" # ccxt Futures gösterimi (Örn: Bitcoin / Tether)
LEVERAGE = 5 # 5x Kaldıraç
TOTAL_CAPITAL = 1000 # Toplam bakiye ($)
RISK_PERCENTAGE = 0.10 # %10 Risk 
# Bu durumda pozisyon için ayrılacak marjin = 100$, 
# 5x Kaldıraçla birlikte toplam açılacak pozisyon büyüklüğü = 500$ olacaktır.

# Testnet modunda çalışmak için True, gerçek hesap için False yapın.
TESTNET = True
