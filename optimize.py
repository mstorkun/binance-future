"""
Donchian breakout stratejisi için parametre tarama.

backtest.run_backtest() kullanır (DRY) — komisyon, slippage, funding modeli orada.
Config sabitleri override edilir, try/finally ile geri yüklenir.
"""

import pandas as pd
import config
from backtest import run_backtest, fetch_history_with_daily


PARAM_GRID = {
    "DONCHIAN_PERIOD": [15, 20, 30, 55],
    "VOLUME_MULT":     [1.2, 1.5, 1.8, 2.0],
    "SL_ATR_MULT":     [1.5, 2.0, 2.5],
}


def run_with_params(df_4h, df_1d, donchian, vol_mult, sl_mult):
    saved = (config.DONCHIAN_PERIOD, config.VOLUME_MULT, config.SL_ATR_MULT)
    config.DONCHIAN_PERIOD = donchian
    config.VOLUME_MULT     = vol_mult
    config.SL_ATR_MULT     = sl_mult
    try:
        trades = run_backtest(df_4h, df_1d)
    finally:
        config.DONCHIAN_PERIOD, config.VOLUME_MULT, config.SL_ATR_MULT = saved

    if trades.empty:
        return None
    return {
        "trades":    len(trades),
        "win_rate":  (trades["pnl"] > 0).sum() / len(trades) * 100,
        "total_pnl": trades["pnl"].sum(),
        "max_dd":    (trades["balance"].cummax() - trades["balance"]).max(),
    }


if __name__ == "__main__":
    df_4h, df_1d = fetch_history_with_daily(years=3)
    print(f"\n4H bar: {len(df_4h)} | 1D bar: {len(df_1d)}\n")

    configs = [
        (d, v, s)
        for d in PARAM_GRID["DONCHIAN_PERIOD"]
        for v in PARAM_GRID["VOLUME_MULT"]
        for s in PARAM_GRID["SL_ATR_MULT"]
    ]
    print(f"{len(configs)} konfigurasyon test ediliyor...\n")

    results = []
    for idx, (d, v, s) in enumerate(configs, 1):
        res = run_with_params(df_4h, df_1d, d, v, s)
        if res:
            res.update({"donchian": d, "vol_mult": v, "sl_mult": s})
            results.append(res)
        if idx % 10 == 0:
            print(f"  {idx}/{len(configs)} bitti...")

    rdf = pd.DataFrame(results)
    rdf["score"] = rdf["total_pnl"] / (rdf["max_dd"] + 1)
    rdf = rdf.sort_values("score", ascending=False)

    print("\n=== EN IYI 10 KONFIGURASYON (PnL/DD orani) ===")
    print(rdf.head(10).to_string(index=False))
    print("\n=== EN YUKSEK PnL ===")
    print(rdf.sort_values("total_pnl", ascending=False).head(5).to_string(index=False))

    rdf.to_csv("optimize_results.csv", index=False)
    print("\nDetaylar: optimize_results.csv")
