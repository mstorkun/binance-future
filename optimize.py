"""
Parametre tarama: en iyi konfigürasyonu bul.
"""
import pandas as pd
import config
import indicators as ind
import strategy as strat
import risk as r
from backtest import fetch_long_history


def run_with_params(df, sl_mult, trail_giveback, trail_activate_atr, adx_thresh):
    """Verilen parametrelerle backtest."""
    df = ind.add_indicators(df)
    trades = []
    balance = config.CAPITAL_USDT

    # Geçici parametre override
    orig_adx = config.ADX_THRESH
    orig_sl  = config.SL_ATR_MULT
    config.ADX_THRESH  = adx_thresh
    config.SL_ATR_MULT = sl_mult

    i = 2
    while i < len(df) - 1:
        window = df.iloc[: i + 1]
        signal = strat.get_signal(window)
        if signal is None:
            i += 1
            continue

        entry_bar = df.iloc[i + 1]
        entry     = entry_bar["open"]
        atr       = df.iloc[i]["atr"]
        size      = r.position_size(balance, atr, entry)
        initial_sl = entry - sl_mult * atr if signal == "long" else entry + sl_mult * atr

        current_sl = initial_sl
        extreme    = entry
        result     = None
        exit_price = None
        exit_bar   = i + 1

        for j in range(i + 2, len(df)):
            bar      = df.iloc[j]
            window_j = df.iloc[: j + 1]

            if strat.check_exit(window_j, signal):
                result     = "trend_exit"
                exit_price = bar["open"]
                exit_bar   = j
                break

            if signal == "long":
                if bar["high"] > extreme:
                    extreme = bar["high"]
                gain = extreme - entry
                # Trailing yalnızca kâr > activate_atr * ATR olduğunda devreye girer
                if gain > trail_activate_atr * atr:
                    trail = extreme - gain * trail_giveback
                    if trail > current_sl:
                        current_sl = trail
                if bar["low"] <= current_sl:
                    result, exit_price, exit_bar = "sl", current_sl, j
                    break
            else:
                if bar["low"] < extreme:
                    extreme = bar["low"]
                gain = entry - extreme
                if gain > trail_activate_atr * atr:
                    trail = extreme + gain * trail_giveback
                    if trail < current_sl:
                        current_sl = trail
                if bar["high"] >= current_sl:
                    result, exit_price, exit_bar = "sl", current_sl, j
                    break

        if result is None:
            i += 1
            continue

        if signal == "long":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        notional = (entry + exit_price) * size
        pnl -= notional * (0.0004 + 0.0005)  # komisyon + slippage

        balance += pnl
        trades.append({"pnl": pnl, "balance": balance, "result": result})
        i = exit_bar + 1

    config.ADX_THRESH  = orig_adx
    config.SL_ATR_MULT = orig_sl

    if not trades:
        return None
    tdf = pd.DataFrame(trades)
    return {
        "trades":    len(tdf),
        "win_rate":  (tdf["pnl"] > 0).sum() / len(tdf) * 100,
        "total_pnl": tdf["pnl"].sum(),
        "max_dd":    (tdf["balance"].cummax() - tdf["balance"]).max(),
    }


if __name__ == "__main__":
    print("Veri cekiliyor...")
    df = fetch_long_history(years=3)
    print(f"{len(df)} bar | {df.index[0]} - {df.index[-1]}\n")

    configs = []
    for sl_mult in [1.5, 2.0, 2.5]:
        for trail_giveback in [0.15, 0.20, 0.30, 0.40]:
            for trail_activate in [0.0, 1.0, 1.5]:
                for adx in [18, 20, 25]:
                    configs.append((sl_mult, trail_giveback, trail_activate, adx))

    print(f"{len(configs)} konfigurasyon test ediliyor...\n")
    results = []
    for idx, (sl, tg, ta, adx) in enumerate(configs):
        res = run_with_params(df, sl, tg, ta, adx)
        if res:
            res.update({"sl_mult": sl, "trail_giveback": tg, "trail_activate": ta, "adx": adx})
            results.append(res)
        if (idx + 1) % 20 == 0:
            print(f"  {idx+1}/{len(configs)} bitti...")

    rdf = pd.DataFrame(results)
    rdf["score"] = rdf["total_pnl"] / (rdf["max_dd"] + 1)  # PnL/DD oranı
    rdf = rdf.sort_values("score", ascending=False)

    print("\n=== EN IYI 10 KONFIGURASYON (PnL/DD orani) ===")
    print(rdf.head(10).to_string(index=False))
    print("\n=== EN YUKSEK PnL ===")
    print(rdf.sort_values("total_pnl", ascending=False).head(5).to_string(index=False))
