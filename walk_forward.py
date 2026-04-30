"""
Walk-forward analiz: parametreleri train segmentinde optimize et,
test segmentinde gerçek performansı ölç.

Donchian breakout stratejisi için. strategy.py'nin get_signal/check_exit/trailing_stop
API'sine bağlı; parametreler config monkey-patch ile değiştirilir.
"""

import pandas as pd

import config
from backtest import fetch_funding_history, run_backtest, fetch_history_with_daily


# === Yardımcılar ===

def _override(donchian, vol_mult, sl_mult):
    """Config sabitlerini override et — testten sonra eski değere döndürmek için tuple döner."""
    saved = (config.DONCHIAN_PERIOD, config.VOLUME_MULT, config.SL_ATR_MULT)
    config.DONCHIAN_PERIOD = donchian
    config.VOLUME_MULT     = vol_mult
    config.SL_ATR_MULT     = sl_mult
    return saved


def _restore(saved):
    config.DONCHIAN_PERIOD, config.VOLUME_MULT, config.SL_ATR_MULT = saved


def run_segment(df_4h, df_1d, donchian, vol_mult, sl_mult, funding_rates=None,
                warmup_skip_ts=None):
    """
    Bir segmentte verilen parametrelerle backtest.
    `warmup_skip_ts` verilirse, o timestamp'ten ÖNCE açılan trade'ler sayılmaz.
    """
    saved = _override(donchian, vol_mult, sl_mult)
    try:
        trades = run_backtest(df_4h, df_1d, funding_rates)
    finally:
        _restore(saved)

    if trades.empty:
        return None

    if warmup_skip_ts is not None and "entry_time" in trades.columns:
        trades = trades[trades["entry_time"] >= warmup_skip_ts].reset_index(drop=True)
        if trades.empty:
            return None

    return {
        "trades":    len(trades),
        "win_rate":  (trades["pnl"] > 0).sum() / len(trades) * 100,
        "total_pnl": trades["pnl"].sum(),
        "max_dd":    (trades["balance"].cummax() - trades["balance"]).max() if "balance" in trades.columns else 0.0,
    }


def find_best_params(df_train_4h, df_train_1d, funding_rates=None):
    """Train segmentinde grid arama."""
    best = None
    for donchian in [15, 20, 30]:
        for vol_mult in [1.2, 1.5, 2.0]:
            for sl_mult in [1.5, 2.0, 2.5]:
                res = run_segment(df_train_4h, df_train_1d, donchian, vol_mult, sl_mult, funding_rates)
                if res is None:
                    continue
                score = res["total_pnl"] / (res["max_dd"] + 1)
                if best is None or score > best["score"]:
                    best = {
                        "donchian": donchian, "vol_mult": vol_mult, "sl_mult": sl_mult,
                        "score": score, **res,
                    }
    return best


# === Walk-forward döngü ===

def _slice_daily(df_1d, start_ts, end_ts):
    return df_1d.loc[(df_1d.index >= start_ts) & (df_1d.index <= end_ts)]


def walk_forward(df_4h, df_1d, funding_rates=None, train_bars=3000, test_bars=1000,
                 roll_bars=1000, warmup_bars=200):
    """
    Test penceresinden önce `warmup_bars` kadar bar prepend edilir, böylece
    indikatörler test'e girmeden önce ısınmış olur. Warmup bar'larında işlem
    sayılmaz; sadece test bölümündeki PnL ölçülür.
    """
    results = []
    start = 0
    period = 1
    while start + train_bars + test_bars <= len(df_4h):
        train_end = start + train_bars
        test_end  = train_end + test_bars

        # Warmup buffer: test öncesi train'in son `warmup_bars` barını prepend et
        warmup_start = max(train_end - warmup_bars, start)
        df_test_4h_full = df_4h.iloc[warmup_start:test_end]   # warmup + test
        df_train_4h     = df_4h.iloc[start:train_end]
        df_test_4h      = df_test_4h_full                      # backtest motoru warmup'ı kullanır
        # Test PnL'sini sadece "warmup sonrası" kısımdan ölçeceğiz
        warmup_count    = train_end - warmup_start

        df_train_1d = _slice_daily(df_1d, df_train_4h.index[0], df_train_4h.index[-1])
        df_test_1d  = _slice_daily(df_1d, df_test_4h.index[0],  df_test_4h.index[-1])

        print(f"\n--- Periyot {period} ---")
        print(f"  Train: {df_train_4h.index[0]} - {df_train_4h.index[-1]} ({len(df_train_4h)} bar)")
        print(f"  Test : {df_test_4h.index[0]} - {df_test_4h.index[-1]} ({len(df_test_4h)} bar)")

        best = find_best_params(df_train_4h, df_train_1d, funding_rates)
        if best is None:
            print("  Train'de işlem yok, atlandı.")
            start += roll_bars
            period += 1
            continue

        test_res = run_segment(df_test_4h, df_test_1d,
                               best["donchian"], best["vol_mult"], best["sl_mult"], funding_rates,
                               warmup_skip_ts=df_4h.index[train_end] if warmup_count > 0 else None)

        print(f"  Best train: donchian={best['donchian']} vol_mult={best['vol_mult']} sl_mult={best['sl_mult']}")
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
    df_4h, df_1d = fetch_history_with_daily(years=3)
    funding = fetch_funding_history(years=3)
    print(f"\n4H bar: {len(df_4h)} | 1D bar: {len(df_1d)} | funding: {len(funding)}\n")

    # 18 ay train, 3 ay test, 3 ay roll → 8+ dönem (3 yıl veride)
    results = walk_forward(df_4h, df_1d, funding, train_bars=3000, test_bars=500, roll_bars=500)

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
