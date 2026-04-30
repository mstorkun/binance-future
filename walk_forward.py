"""
Walk-forward analiz: Veriyi pencerelere böl, her pencerede train+test yap.
Overfitting riskini ölçer.

- Train window: 18 ay (4500 bar @ 4H)
- Test window:   6 ay (1100 bar @ 4H)
- Roll: 6 ay
"""

import pandas as pd
import config
import indicators as ind
from backtest import fetch_long_history

LONG, SHORT = "long", "short"

# === Strateji mantığı (strategy.py'ye bağımlı değil) ===

def get_signal(df, adx_thresh):
    if len(df) < 3:
        return None
    prev, prev2 = df.iloc[-2], df.iloc[-3]
    trend_up   = prev["ema_fast"] > prev["ema_slow"]
    trend_down = prev["ema_fast"] < prev["ema_slow"]
    flipped_up   = trend_up   and prev2["ema_fast"] <= prev2["ema_slow"]
    flipped_down = trend_down and prev2["ema_fast"] >= prev2["ema_slow"]
    adx_ok    = prev["adx"] > adx_thresh
    rsi_long  = config.RSI_LONG_MIN  <= prev["rsi"] <= config.RSI_LONG_MAX
    rsi_short = config.RSI_SHORT_MIN <= prev["rsi"] <= config.RSI_SHORT_MAX
    if flipped_up and adx_ok and rsi_long:
        return LONG
    if flipped_down and adx_ok and rsi_short:
        return SHORT
    return None


def check_exit(df, side):
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    return (prev["ema_fast"] < prev["ema_slow"]) if side == LONG else (prev["ema_fast"] > prev["ema_slow"])


def run_segment(df, sl_mult, trail_giveback, trail_activate, adx_thresh):
    """Tek bir veri segmentinde backtest."""
    df = ind.add_indicators(df)
    if df.empty or len(df) < 5:
        return None

    trades = []
    balance = config.CAPITAL_USDT
    i = 2
    while i < len(df) - 1:
        signal = get_signal(df.iloc[: i + 1], adx_thresh)
        if signal is None:
            i += 1
            continue

        entry = df.iloc[i + 1]["open"]
        atr   = df.iloc[i]["atr"]
        size  = (balance * config.RISK_PER_TRADE_PCT) / (atr * sl_mult)
        size  = round(size, 4)
        initial_sl = entry - sl_mult * atr if signal == LONG else entry + sl_mult * atr

        current_sl = initial_sl
        extreme    = entry
        result, exit_price, exit_bar = None, None, i + 1

        for j in range(i + 2, len(df)):
            bar = df.iloc[j]
            if check_exit(df.iloc[: j + 1], signal):
                result, exit_price, exit_bar = "trend", bar["open"], j
                break
            if signal == LONG:
                if bar["high"] > extreme:
                    extreme = bar["high"]
                gain = extreme - entry
                if gain > trail_activate * atr:
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
                if gain > trail_activate * atr:
                    trail = extreme + gain * trail_giveback
                    if trail < current_sl:
                        current_sl = trail
                if bar["high"] >= current_sl:
                    result, exit_price, exit_bar = "sl", current_sl, j
                    break

        if result is None:
            i += 1
            continue

        pnl = (exit_price - entry) * size if signal == LONG else (entry - exit_price) * size
        notional = (entry + exit_price) * size
        pnl -= notional * 0.0009  # komisyon + slippage

        balance += pnl
        trades.append({"pnl": pnl, "balance": balance})
        i = exit_bar + 1

    if not trades:
        return None
    tdf = pd.DataFrame(trades)
    return {
        "trades":    len(tdf),
        "win_rate":  (tdf["pnl"] > 0).sum() / len(tdf) * 100,
        "total_pnl": tdf["pnl"].sum(),
        "max_dd":    (tdf["balance"].cummax() - tdf["balance"]).max(),
    }


def find_best_params(df_train):
    """Train segmentinde en iyi parametreleri bul."""
    best = None
    for sl in [1.5, 2.0, 2.5]:
        for tg in [0.15, 0.20, 0.30]:
            for ta in [0.0, 1.0]:
                for adx in [18, 20, 25]:
                    res = run_segment(df_train, sl, tg, ta, adx)
                    if res is None:
                        continue
                    score = res["total_pnl"] / (res["max_dd"] + 1)
                    if best is None or score > best["score"]:
                        best = {"sl": sl, "tg": tg, "ta": ta, "adx": adx,
                                "score": score, **res}
    return best


def walk_forward(df, train_bars=4500, test_bars=1100, roll_bars=1100):
    """Walk-forward döngü."""
    results = []
    start = 0
    period = 1
    while start + train_bars + test_bars <= len(df):
        train_end = start + train_bars
        test_end  = train_end + test_bars

        df_train = df.iloc[start:train_end]
        df_test  = df.iloc[train_end:test_end]

        print(f"\n--- Periyot {period} ---")
        print(f"  Train: {df_train.index[0]} - {df_train.index[-1]} ({len(df_train)} bar)")
        print(f"  Test : {df_test.index[0]} - {df_test.index[-1]} ({len(df_test)} bar)")

        best = find_best_params(df_train)
        if best is None:
            print("  Train'de işlem yok, atlandı.")
            start += roll_bars
            period += 1
            continue

        # En iyi parametrelerle test segmentini koştur
        test_res = run_segment(df_test, best["sl"], best["tg"], best["ta"], best["adx"])

        print(f"  En iyi train: sl={best['sl']} tg={best['tg']} ta={best['ta']} adx={best['adx']}")
        print(f"  Train: {best['trades']} trade, %{best['win_rate']:.1f} WR, PnL={best['total_pnl']:.1f}, DD={best['max_dd']:.1f}")
        if test_res:
            print(f"  Test : {test_res['trades']} trade, %{test_res['win_rate']:.1f} WR, PnL={test_res['total_pnl']:.1f}, DD={test_res['max_dd']:.1f}")
            results.append({"period": period, **{f"train_{k}":v for k,v in best.items()}, **{f"test_{k}":v for k,v in test_res.items()}})
        else:
            print(f"  Test : işlem yok")

        start += roll_bars
        period += 1

    return pd.DataFrame(results)


if __name__ == "__main__":
    print("Veri cekiliyor (3 yil)...")
    df = fetch_long_history(years=3)
    print(f"Toplam {len(df)} bar\n")

    results = walk_forward(df, train_bars=3000, test_bars=1000, roll_bars=1000)

    if results.empty:
        print("Hicbir periyot tamamlanamadi.")
    else:
        print("\n\n=== WALK-FORWARD OZET ===")
        cols = ["period", "train_total_pnl", "train_max_dd", "train_win_rate",
                "test_total_pnl", "test_max_dd", "test_win_rate", "test_trades"]
        print(results[cols].to_string(index=False))

        print(f"\nTrain ortalama PnL: {results['train_total_pnl'].mean():.1f}")
        print(f"Test  ortalama PnL: {results['test_total_pnl'].mean():.1f}")
        print(f"Train>Test farki  : {(results['train_total_pnl'] - results['test_total_pnl']).mean():.1f} (overfitting gostergesi)")

        positive_test = (results['test_total_pnl'] > 0).sum()
        print(f"Test'te karli periyot: {positive_test}/{len(results)}")

        results.to_csv("walk_forward_results.csv", index=False)
        print("\nDetaylar: walk_forward_results.csv")
