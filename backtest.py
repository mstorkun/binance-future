"""
Backtest — Donchian breakout + hacim + 1D filtre.
Çıkış koşulları:
  1. Trailing stop kırıldı  (kazancın %15'i geri verildi)
  2. Erken trend dönüşü     (10-bar Donchian ters kırıldı)
  3. İlk SL kırıldı         (ATR tabanlı)
Komisyon ve slippage PnL'den düşülür.
Kullanım:
    python backtest.py
"""

import ccxt
import pandas as pd
import config
import indicators as ind
import strategy as strat
import risk as r


def run_backtest(df: pd.DataFrame, df_daily: pd.DataFrame | None = None) -> pd.DataFrame:
    df = ind.add_indicators(df)
    if df_daily is not None and not df_daily.empty:
        df = ind.add_daily_trend(df, df_daily)
    trades = []
    balance = config.CAPITAL_USDT

    i = 2
    while i < len(df) - 1:
        window = df.iloc[: i + 1]
        signal = strat.get_signal(window)

        if signal is None:
            i += 1
            continue

        entry_bar  = df.iloc[i + 1]
        entry      = entry_bar["open"]
        atr        = df.iloc[i]["atr"]
        initial_sl, _ = r.sl_tp_prices(entry, atr, signal)
        size       = r.position_size(balance, atr, entry)

        current_sl = initial_sl
        extreme    = entry  # long → en yüksek, short → en düşük
        result     = None
        exit_price = None
        exit_bar   = i + 1

        for j in range(i + 2, len(df)):
            bar    = df.iloc[j]
            window_j = df.iloc[: j + 1]

            # Trend tersine döndü mü?
            if strat.check_exit(window_j, signal):
                result     = "trend_exit"
                exit_price = bar["open"]
                exit_bar   = j
                break

            if signal == "long":
                if bar["high"] > extreme:
                    extreme = bar["high"]
                # Trailing stop sadece kârda aktif olur
                if extreme > entry:
                    trail = strat.trailing_stop(entry, extreme, signal)
                    if trail > current_sl:
                        current_sl = trail

                if bar["low"] <= current_sl:
                    result     = "sl"
                    exit_price = current_sl
                    exit_bar   = j
                    break

            else:  # short
                if bar["low"] < extreme:
                    extreme = bar["low"]
                if extreme < entry:
                    trail = strat.trailing_stop(entry, extreme, signal)
                    if trail < current_sl:
                        current_sl = trail

                if bar["high"] >= current_sl:
                    result     = "sl"
                    exit_price = current_sl
                    exit_bar   = j
                    break

        if result is None:
            i += 1
            continue

        if signal == "long":
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size

        # Komisyon: Binance Futures taker fee %0.04 (giriş + çıkış = %0.08)
        notional = (entry + exit_price) * size
        commission = notional * 0.0004
        # Slippage: 5 bps her tarafta = 10 bps round-trip
        slippage = notional * 0.0005
        pnl -= (commission + slippage)

        balance += pnl
        trades.append({
            "entry_time":  entry_bar.name,
            "exit_time":   df.index[exit_bar],
            "signal":      signal,
            "entry":       round(entry, 2),
            "exit":        round(exit_price, 2),
            "extreme":     round(extreme, 2),
            "result":      result,
            "pnl":         round(pnl, 2),
            "balance":     round(balance, 2),
        })

        i = exit_bar + 1

    return pd.DataFrame(trades)


def print_summary(trades: pd.DataFrame):
    if trades.empty:
        print("İşlem yok.")
        return

    total    = len(trades)
    wins     = len(trades[trades["pnl"] > 0])
    losses   = len(trades[trades["pnl"] <= 0])
    win_rate = wins / total * 100
    total_pnl = trades["pnl"].sum()
    max_dd   = (trades["balance"].cummax() - trades["balance"]).max()
    trend_exits = len(trades[trades["result"] == "trend_exit"])
    sl_hits     = len(trades[trades["result"] == "sl"])

    print(f"\n{'='*45}")
    print(f"Toplam işlem    : {total}")
    print(f"Kazanan         : {wins}  ({win_rate:.1f}%)")
    print(f"Kaybeden        : {losses}")
    print(f"Trend çıkışı    : {trend_exits}")
    print(f"SL çıkışı       : {sl_hits}")
    print(f"Toplam PnL      : {total_pnl:.2f} USDT")
    print(f"Son bakiye      : {trades['balance'].iloc[-1]:.2f} USDT")
    print(f"Max Drawdown    : {max_dd:.2f} USDT")
    print(f"{'='*45}\n")


def _fetch_paginated(timeframe: str, years: int) -> pd.DataFrame:
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    tf_ms = {"4h": 4 * 60 * 60 * 1000, "1h": 60 * 60 * 1000, "1d": 24 * 60 * 60 * 1000}
    step  = tf_ms.get(timeframe, 4 * 60 * 60 * 1000)
    total_bars = int(years * 365 * 24 * 60 * 60 * 1000 / step)

    since = exchange.milliseconds() - total_bars * step
    all_bars = []
    print(f"  {timeframe}: ~{total_bars} bar...")

    while since < exchange.milliseconds() - step:
        batch = exchange.fetch_ohlcv(config.SYMBOL, timeframe, since=since, limit=1000)
        if not batch:
            break
        all_bars.extend(batch)
        since = batch[-1][0] + step

    df = pd.DataFrame(all_bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df[~df.index.duplicated()]


def fetch_long_history(years: int = 3) -> pd.DataFrame:
    """4H barlarını döndürür (geriye uyumluluk için)."""
    return _fetch_paginated(config.TIMEFRAME, years)


def fetch_history_with_daily(years: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hem 4H hem 1D verisi çek (Donchian + daily_trend için)."""
    print(f"Veri çekiliyor ({years} yıl)...")
    df_4h  = _fetch_paginated(config.TIMEFRAME, years)
    df_1d  = _fetch_paginated(config.DAILY_TIMEFRAME, years)
    return df_4h, df_1d


if __name__ == "__main__":
    df_4h, df_1d = fetch_history_with_daily(years=3)
    print(f"4H: {df_4h.index[0]} - {df_4h.index[-1]} ({len(df_4h)} bar)")
    print(f"1D: {df_1d.index[0]} - {df_1d.index[-1]} ({len(df_1d)} bar)")

    print("\nBacktest çalıştırılıyor...")
    trades = run_backtest(df_4h, df_1d)
    print_summary(trades)

    if not trades.empty:
        trades.to_csv("backtest_results.csv", index=False)
        print("Detaylar: backtest_results.csv")
