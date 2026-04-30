import pandas as pd

def simple_moving_average_strategy(df: pd.DataFrame, short_window=10, long_window=50):
    """
    Basit Hareketli Ortalama (SMA) Kesişim Stratejisi
    - Kısa MA (10), Uzun MA'yı (50) yukarı keserse: LONG (Alış) Sinyali
    - Kısa MA, Uzun MA'yı aşağı keserse: SHORT (Satış) Sinyali
    """
    # Kapanış fiyatları üzerinden ortalamaları hesapla
    df['SMA_short'] = df['close'].rolling(window=short_window).mean()
    df['SMA_long'] = df['close'].rolling(window=long_window).mean()

    # Yeterli veri yoksa işlem yapma
    if len(df) < long_window + 1:
        return "NEUTRAL"
    
    # Bir önceki ve şimdiki (son kapanmış) mumun ortalamalarına bak
    prev_short = df['SMA_short'].iloc[-3]
    prev_long = df['SMA_long'].iloc[-3]
    
    curr_short = df['SMA_short'].iloc[-2]
    curr_long = df['SMA_long'].iloc[-2]

    # Yukarı Kesişim (Golden Cross)
    if prev_short <= prev_long and curr_short > curr_long:
        return "LONG"
    
    # Aşağı Kesişim (Death Cross)
    elif prev_short >= prev_long and curr_short < curr_long:
        return "SHORT"
    
    # Kesişim yoksa beklemede kal
    return "NEUTRAL"
