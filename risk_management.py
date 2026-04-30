def calculate_position_size(capital, risk_percentage, leverage, current_price):
    """
    Belirlenen riske göre ne kadar coin alınması/satılması gerektiğini hesaplar.
    
    Sermaye (Capital) = 1000$
    Risk Oranı = %10 (0.10) => Riske atılan miktar (Teminat) = 100$
    Kaldıraç = 5x
    Toplam Alım Gücü = 500$
    
    Örnek: Bitcoin fiyatı = 50000$ ise
    Alınacak BTC miktarı = 500 / 50000 = 0.01 BTC
    """
    margin_amount = capital * risk_percentage
    total_position_value = margin_amount * leverage
    
    # Miktarı mevcut fiyata bölerek coin adetini buluyoruz
    amount = total_position_value / current_price
    
    return amount, margin_amount
