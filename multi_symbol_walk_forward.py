"""
Çoklu sembol walk-forward: BTC, ETH, SOL, BNB için aynı WF analizi.

Mantık:
- Her sembolde 18 ay train, 3 ay test, 3 ay roll → ~7 dönem
- Her dönem için en iyi parametreyi train'de bul, test'te uygula
- Tüm sembollerin test ortalamaları karşılaştırılır

Eğer 3-4 sembolde test ortalaması POZİTİF → strateji gerçek edge
Eğer 1-2 sembolde → karışık, kullanılabilir değil
Eğer 0 sembolde → strateji terk
"""

import pandas as pd
import config
from backtest import _fetch_paginated
from walk_forward import walk_forward
from multi_symbol_backtest import SYMBOLS


def fetch_for_symbol(symbol: str, years: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    saved = config.SYMBOL
    config.SYMBOL = symbol
    try:
        df_4h = _fetch_paginated(config.TIMEFRAME, years)
        df_1d = _fetch_paginated(config.DAILY_TIMEFRAME, years)
    finally:
        config.SYMBOL = saved
    return df_4h, df_1d


def wf_for_symbol(symbol: str, years: int = 3) -> dict:
    print(f"\n========== {symbol} ==========")
    df_4h, df_1d = fetch_for_symbol(symbol, years)
    print(f"4H: {len(df_4h)} bar | 1D: {len(df_1d)} bar")

    saved = config.SYMBOL
    config.SYMBOL = symbol
    try:
        results = walk_forward(df_4h, df_1d, train_bars=3000, test_bars=500, roll_bars=500)
    finally:
        config.SYMBOL = saved

    if results.empty:
        return {"symbol": symbol, "periods": 0, "test_avg": 0, "test_pos": 0, "test_total": 0}

    return {
        "symbol":     symbol,
        "periods":    len(results),
        "test_avg":   results["test_total_pnl"].mean(),
        "test_total": results["test_total_pnl"].sum(),
        "test_pos":   (results["test_total_pnl"] > 0).sum(),
        "test_max_dd_avg": results["test_max_dd"].mean(),
        "train_avg":  results["train_total_pnl"].mean(),
    }


if __name__ == "__main__":
    summaries = []
    for sym in SYMBOLS:
        try:
            res = wf_for_symbol(sym, years=3)
            summaries.append(res)
        except Exception as e:
            print(f"{sym} HATA: {e}")

    if not summaries:
        print("Hicbir sembolde sonuc alinamadi.")
        exit(1)

    df = pd.DataFrame(summaries)
    df["test_pos_ratio"] = df["test_pos"] / df["periods"] * 100
    df["overfitting"] = df["train_avg"] - df["test_avg"]

    print("\n\n=== COKLU SEMBOL WALK-FORWARD OZET ===")
    cols = ["symbol", "periods", "train_avg", "test_avg", "test_total",
            "test_pos", "test_pos_ratio", "test_max_dd_avg", "overfitting"]
    print(df[cols].to_string(index=False))

    avg_test_pnl = df["test_avg"].mean()
    pos_symbols  = (df["test_avg"] > 0).sum()
    total_pos_periods = df["test_pos"].sum()
    total_periods     = df["periods"].sum()

    print(f"\nTest ortalama PnL (semboller arasi): {avg_test_pnl:.1f} USDT")
    print(f"Test'te pozitif ortalamali sembol: {pos_symbols}/{len(df)}")
    print(f"Tum donem ve sembollerde pozitif: {total_pos_periods}/{total_periods}")

    df.to_csv("multi_symbol_walk_forward_results.csv", index=False)
    print("\nDetaylar: multi_symbol_walk_forward_results.csv")

    print("\n--- VERDIKT ---")
    if pos_symbols >= 3 and avg_test_pnl > 0:
        print("GUCLU: 3+ sembolde test ortalamasi pozitif. Strateji gercek bir kenar tasiyor.")
        print("Sonraki: parametre stabilite haritasi + Monte Carlo + testnet'te paper trading.")
    elif pos_symbols == 2:
        print("ZAYIF: 2/4 sembolde pozitif. Kullanilabilir degil, daha cok iyilestirme gerekli.")
    else:
        print("OLUMSUZ: Coklu sembol WF basarisiz. Strateji ya BTC-spesifik sansa dayaniyor")
        print("ya da temel mantik calismiyor. Donchian breakout'u terk etmeyi dusunmeli.")
