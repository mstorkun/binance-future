"""
Basit vektörel backtest — gerçek emir simülasyonu değil, sinyal bazlı P&L hesabı.
Kullanım:
    python backtest.py
"""

import ccxt
import pandas as pd
import config
import indicators as ind
import strategy as strat
import risk as r


def run_backtest(df: pd.DataFrame) -> pd.DataFrame:
    df = ind.add_indicators(df)
    trades = []
    balance = config.CAPITAL_USDT

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
        sl, tp    = r.sl_tp_prices(entry, atr, signal)
        size      = r.position_size(balance, atr, entry)

        # İlerleyen barlarda SL/TP kontrolü
        result = None
        for j in range(i + 1, min(i + 50, len(df))):
            bar = df.iloc[j]
            if signal == "long":
                if bar["low"] <= sl:
                    result = "sl"
                    exit_price = sl
                    break
                if bar["high"] >= tp:
                    result = "tp"
                    exit_price = tp
                    break
            else:
                if bar["high"] >= sl:
                    result = "sl"
                    exit_price = sl
                    break
                if bar["low"] <= tp:
                    result = "tp"
                    exit_price = tp
                    break

        if result is None:
            i += 1
            continue

        if signal == "long":
            pnl = (exit_price - entry) * size * config.LEVERAGE
        else:
            pnl = (entry - exit_price) * size * config.LEVERAGE

        balance += pnl
        trades.append({
            "entry_time": entry_bar.name,
            "signal":     signal,
            "entry":      entry,
            "exit":       exit_price,
            "result":     result,
            "pnl":        round(pnl, 2),
            "balance":    round(balance, 2),
        })
        i = j + 1

    return pd.DataFrame(trades)


def print_summary(trades: pd.DataFrame):
    if trades.empty:
        print("İşlem yok.")
        return

    total    = len(trades)
    wins     = len(trades[trades["result"] == "tp"])
    losses   = len(trades[trades["result"] == "sl"])
    win_rate = wins / total * 100
    total_pnl = trades["pnl"].sum()
    max_dd   = (trades["balance"].cummax() - trades["balance"]).max()

    print(f"\n{'='*40}")
    print(f"Toplam işlem : {total}")
    print(f"Kazanan      : {wins}  ({win_rate:.1f}%)")
    print(f"Kaybeden     : {losses}")
    print(f"Toplam PnL   : {total_pnl:.2f} USDT")
    print(f"Son bakiye   : {trades['balance'].iloc[-1]:.2f} USDT")
    print(f"Max Drawdown : {max_dd:.2f} USDT")
    print(f"{'='*40}\n")


if __name__ == "__main__":
    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    print("Veri çekiliyor...")
    raw = exchange.fetch_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=1000)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)

    print("Backtest çalıştırılıyor...")
    trades = run_backtest(df)
    print_summary(trades)

    if not trades.empty:
        trades.to_csv("backtest_results.csv", index=False)
        print("Sonuçlar backtest_results.csv dosyasına kaydedildi.")
