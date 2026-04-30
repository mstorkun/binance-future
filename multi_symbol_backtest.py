"""
Çoklu sembol backtest: aynı stratejiyi BTC, ETH, SOL, BNB üzerinde test eder.

Mantık:
- Eğer strateji yalnızca BTC'de çalışıyorsa → veri-spesifik (şanslı dönem).
- 3+ sembolde pozitif sonuç → stratejik kenar (edge) gerçek olabilir.
- Hepsinde negatif → stratejiyi bırak.

Aynı parametre seti tüm sembollerde kullanılır. Sembol başına farklı parametre
seçmek = overfitting (her sembol için kendi geçmişine fit olur).
"""

import pandas as pd
import config
from backtest import _fetch_paginated, fetch_funding_history, run_backtest


SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]


def fetch_symbol_data(symbol: str, years: int = 3) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Bir sembol için 4H + 1D + funding verisi çek."""
    saved_symbol = config.SYMBOL
    config.SYMBOL = symbol
    try:
        df_4h = _fetch_paginated(config.TIMEFRAME, years)
        df_1d = _fetch_paginated(config.DAILY_TIMEFRAME, years)
        funding = fetch_funding_history(years)
    finally:
        config.SYMBOL = saved_symbol
    return df_4h, df_1d, funding


def backtest_symbol(symbol: str, years: int = 3) -> dict:
    saved_symbol = config.SYMBOL
    config.SYMBOL = symbol
    try:
        print(f"\n>>> {symbol} verisi cekiliyor...")
        df_4h, df_1d, funding = fetch_symbol_data(symbol, years)
        print(f"  4H: {len(df_4h)} bar | 1D: {len(df_1d)} bar | funding: {len(funding)} kayit")

        if len(df_4h) < 500:
            print(f"  Yetersiz veri, atlandı.")
            return None

        trades = run_backtest(df_4h, df_1d, funding)
    finally:
        config.SYMBOL = saved_symbol

    if trades.empty:
        return {
            "symbol":     symbol,
            "trades":     0,
            "win_rate":   0.0,
            "total_pnl":  0.0,
            "max_dd":     0.0,
            "first_bar":  df_4h.index[0],
            "last_bar":   df_4h.index[-1],
        }

    return {
        "symbol":     symbol,
        "trades":     len(trades),
        "win_rate":   (trades["pnl"] > 0).sum() / len(trades) * 100,
        "total_pnl":  trades["pnl"].sum(),
        "max_dd":     (trades["balance"].cummax() - trades["balance"]).max(),
        "first_bar":  df_4h.index[0],
        "last_bar":   df_4h.index[-1],
    }


if __name__ == "__main__":
    results = []
    for sym in SYMBOLS:
        try:
            res = backtest_symbol(sym, years=3)
            if res:
                results.append(res)
                print(f"  {sym}: {res['trades']} trade | %{res['win_rate']:.1f} WR | "
                      f"PnL={res['total_pnl']:.1f} | DD={res['max_dd']:.1f}")
        except Exception as e:
            print(f"  {sym} HATA: {e}")

    if not results:
        print("\nHiçbir sembolde sonuç alınamadı.")
        exit(1)

    rdf = pd.DataFrame(results)
    rdf["pnl_pct"]  = rdf["total_pnl"] / config.CAPITAL_USDT * 100
    rdf["dd_pct"]   = rdf["max_dd"]    / config.CAPITAL_USDT * 100
    rdf["pnl_dd"]   = rdf["total_pnl"] / (rdf["max_dd"] + 1)

    print("\n\n=== ÇOKLU SEMBOL BACKTEST (3 yıl, aynı parametreler) ===")
    print(rdf[["symbol", "trades", "win_rate", "total_pnl", "max_dd", "pnl_pct", "pnl_dd"]].to_string(index=False))

    pos_count = (rdf["total_pnl"] > 0).sum()
    print(f"\nPozitif PnL veren sembol: {pos_count}/{len(rdf)}")
    print(f"Toplam PnL ortalama : {rdf['total_pnl'].mean():.1f} USDT")
    print(f"Toplam PnL medyan   : {rdf['total_pnl'].median():.1f} USDT")
    print(f"PnL/DD oranı medyan : {rdf['pnl_dd'].median():.2f}")

    rdf.to_csv("multi_symbol_results.csv", index=False)
    print("\nDetaylar: multi_symbol_results.csv")

    # Verdikt
    print("\n--- VERDIKT ---")
    if pos_count >= 3:
        print("Strateji sembollerin cogunda pozitif -> kenar (edge) olabilir, WF/paper ile dogrula.")
    elif pos_count == 2:
        print("Karisik sonuc -> daha fazla test (walk-forward, parametre stabilite) gerekli.")
    else:
        print("Strateji cogu sembolde basarisiz -> BTC sonucu buyuk olasilikla sans.")
