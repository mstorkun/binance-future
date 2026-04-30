import ccxt
import time
import pandas as pd
import config
from risk_management import calculate_position_size
from strategy import simple_moving_average_strategy

def init_exchange():
    """Binance Futures bağlantısını başlatır."""
    exchange = ccxt.binance({
        'apiKey': config.API_KEY,
        'secret': config.API_SECRET,
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future' # Spot yerine Vadeli İşlemler pazarını seçer
        }
    })
    
    # Testnet açıksa sanal borsaya bağlanır
    if config.TESTNET:
        exchange.set_sandbox_mode(True)
        print("Bot TESTNET (Sanal Para) modunda başlatıldı.")
    else:
        print("DİKKAT: Bot GERÇEK PARA modunda çalışıyor!")
        
    return exchange

def fetch_ohlcv(exchange, symbol, timeframe='1h', limit=100):
    """Borsadan geçmiş fiyat mumlarını çeker."""
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def set_leverage(exchange, symbol, leverage):
    """Binance üzerinde işlem çiftinin kaldıraç oranını günceller."""
    try:
        # ccxt formatındaki sembolü binance formatına çevir (BTC/USDT:USDT -> BTCUSDT)
        market = exchange.market(symbol)
        exchange.fapiPrivate_post_leverage({
            'symbol': market['id'],
            'leverage': leverage
        })
        print(f"Kaldıraç başarıyla {leverage}x olarak ayarlandı.")
    except Exception as e:
        print(f"Kaldıraç ayarlanırken uyarı/hata (Zaten ayarlı olabilir): {e}")

def main():
    print("Bot başlatılıyor...")
    
    # Exchange bağlantısı ve piyasa verilerinin yüklenmesi
    exchange = init_exchange()
    exchange.load_markets()
    
    symbol = config.SYMBOL
    leverage = config.LEVERAGE
    capital = config.TOTAL_CAPITAL
    risk_percentage = config.RISK_PERCENTAGE
    
    # Borsa tarafında kaldıracı ayarla
    set_leverage(exchange, symbol, leverage)
    
    current_position = None # "LONG" veya "SHORT" durumunu tutar
    
    print(f"İzlenen Çift: {symbol} | Ana Para: {capital}$ | Risk: %{int(risk_percentage*100)} | Kaldıraç: {leverage}x")

    # Sonsuz Döngü - Bot sürekli çalışır
    while True:
        try:
            print(f"\n[{pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}] Piyasa analiz ediliyor...")
            
            # Fiyatları çek (1 saatlik periyot)
            df = fetch_ohlcv(exchange, symbol, timeframe='1h')
            current_price = float(df['close'].iloc[-1])
            
            # Strateji modülünden al-sat sinyalini hesapla
            signal = simple_moving_average_strategy(df)
            print(f"Güncel {symbol} Fiyatı: {current_price}$ | Sinyal: {signal}")
            
            # 1) EĞER POZİSYONDA DEĞİLSEK VE SİNYAL GELDİYSE İŞLEME GİR
            if current_position is None and signal in ["LONG", "SHORT"]:
                # Ne kadar alınacağını hesapla
                amount, margin = calculate_position_size(capital, risk_percentage, leverage, current_price)
                
                print(f"!!! YENİ İŞLEM FIRSATI BULUNDU !!!")
                print(f"Yön: {signal} | Kullanılan Teminat: {margin}$ | Pozisyon Büyüklüğü: {amount} Adet")
                
                # Emir Gönderimi
                side = "buy" if signal == "LONG" else "sell"
                
                # Binance borsasına market emri gönderiliyor
                # order = exchange.create_market_order(symbol, side, amount)
                # print(f"Emir başarıyla gerçekleşti: {order['id']}")
                
                print(f"--- BİLGİ: Sistem testi için emir simüle edildi. Gerçekte borsa api'sine '{side.upper()}' emri gönderilecekti. ---")
                current_position = signal
                
            # 2) EĞER POZİSYONDAYSAK VE TERS SİNYAL GELDİYSE İŞLEMDEN ÇIK
            elif current_position is not None:
                if (current_position == "LONG" and signal == "SHORT") or \
                   (current_position == "SHORT" and signal == "LONG"):
                    print("Ters sinyal tespit edildi. Mevcut pozisyon kapatılıyor...")
                    
                    # Ters emir vererek pozisyonu kapat
                    # side = "sell" if current_position == "LONG" else "buy"
                    # exchange.create_market_order(symbol, side, amount)
                    
                    current_position = None
                    print("Pozisyon başarıyla kapatıldı. Yeni fırsatlar bekleniyor.")
            
            # Her kontrol arası 5 dakika bekle
            time.sleep(300)
            
        except Exception as e:
            print(f"Bot çalışırken bir hata oluştu: {e}")
            time.sleep(60) # Hata durumunda 1 dakika bekleyip tekrar dener

if __name__ == "__main__":
    main()
