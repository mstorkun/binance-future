"""
Çoklu sembol backtest — DOĞRU sermaye paylaşımı.

DİKKAT: Önceki versiyonda her sembol AYRI 1000 USDT sermaye ile test ediliyordu.
Bu, "1000 USDT'yi 3 sembole böl" portföy senaryosunu yanıltıcı şişirdi.
Doğru: her sembol CAPITAL_USDT / N (paylaştırılmış sermaye) ile başlar.

Mantık:
- Eğer strateji yalnızca BTC'de çalışıyorsa → veri-spesifik (şanslı dönem).
- 3+ sembolde pozitif sonuç → stratejik kenar (edge) gerçek olabilir.
- Hepsinde negatif → stratejiyi bırak.

Aynı parametre seti tüm sembollerde kullanılır.
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


def backtest_symbol(symbol: str, start_balance: float, years: int = 3) -> dict:
    """Tek sembol backtest, verilen sermaye ile."""
    saved_symbol = config.SYMBOL
    config.SYMBOL = symbol
    try:
        print(f"\n>>> {symbol} (sermaye: {start_balance:.0f} USDT)")
        df_4h, df_1d, funding = fetch_symbol_data(symbol, years)
        print(f"  4H: {len(df_4h)} bar | 1D: {len(df_1d)} bar | funding: {len(funding)}")

        if len(df_4h) < 500:
            print(f"  Yetersiz veri, atlandı.")
            return None

        trades = run_backtest(df_4h, df_1d, funding, start_balance=start_balance)
    finally:
        config.SYMBOL = saved_symbol

    if trades.empty:
        return {
            "symbol": symbol, "trades": 0, "win_rate": 0.0,
            "total_pnl": 0.0, "max_dd": 0.0,
            "start_balance": start_balance,
        }

    return {
        "symbol":        symbol,
        "trades":        len(trades),
        "win_rate":      (trades["pnl"] > 0).sum() / len(trades) * 100,
        "total_pnl":     trades["pnl"].sum(),
        "max_dd":        (trades["balance"].cummax() - trades["balance"]).max(),
        "start_balance": start_balance,
    }


if __name__ == "__main__":
    # GERÇEK PORTFÖY: tek sermaye N sembole bölünür
    per_symbol_balance = config.CAPITAL_USDT / len(SYMBOLS)
    print(f"\nToplam sermaye: {config.CAPITAL_USDT} USDT")
    print(f"Sembol başı:    {per_symbol_balance:.2f} USDT ({len(SYMBOLS)} sembol)")

    results = []
    for sym in SYMBOLS:
        try:
            res = backtest_symbol(sym, per_symbol_balance, years=3)
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
    rdf["pnl_pct"]  = rdf["total_pnl"] / rdf["start_balance"] * 100
    rdf["pnl_dd"]   = rdf["total_pnl"] / (rdf["max_dd"] + 1)

    print("\n\n=== PORTFOY BACKTEST (3 yil, paylasilmis sermaye) ===")
    print(rdf[["symbol", "start_balance", "trades", "win_rate",
               "total_pnl", "max_dd", "pnl_pct", "pnl_dd"]].to_string(index=False))

    portfolio_pnl  = rdf["total_pnl"].sum()
    portfolio_dd   = rdf["max_dd"].sum()  # konservatif (eş zamanlı en kötü)
    pnl_pct        = portfolio_pnl / config.CAPITAL_USDT * 100
    pos_count      = (rdf["total_pnl"] > 0).sum()

    print(f"\n--- PORTFOY OZETI ---")
    print(f"Toplam baslangic sermaye : {config.CAPITAL_USDT:.0f} USDT")
    print(f"Toplam PnL (3 yil)       : {portfolio_pnl:+.2f} USDT ({pnl_pct:+.2f}%)")
    print(f"Yillik bilesik (CAGR)    : {((1 + pnl_pct/100) ** (1/3) - 1) * 100:+.2f}%/yil")
    print(f"Konservatif toplam DD    : {portfolio_dd:.2f} USDT")
    print(f"Pozitif sembol           : {pos_count}/{len(rdf)}")

    rdf.to_csv("multi_symbol_results.csv", index=False)
    print("\nDetaylar: multi_symbol_results.csv")
