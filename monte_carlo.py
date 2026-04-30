"""
Monte Carlo trade-shuffle testi.

Backtest işlemlerinin PnL sırasını karıştırır ve olası drawdown dağılımını ölçer.
Bu, tek bir tarihsel sıranın şanslı mı yoksa sağlam mı olduğunu anlamak için kullanılır.
"""

import argparse
import random

import pandas as pd

import config


def _max_drawdown_from_pnls(pnls: list[float], start_balance: float) -> float:
    balance = start_balance
    peak = start_balance
    max_dd = 0.0
    for pnl in pnls:
        balance += pnl
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
    return max_dd


def run_monte_carlo(
    trades: pd.DataFrame,
    iterations: int = 5000,
    start_balance: float = config.CAPITAL_USDT,
    seed: int = 42,
) -> pd.DataFrame:
    if "pnl" not in trades.columns:
        raise ValueError("CSV içinde 'pnl' kolonu olmalı.")

    pnls = [float(x) for x in trades["pnl"].dropna().tolist()]
    if not pnls:
        raise ValueError("Monte Carlo için işlem PnL verisi yok.")

    rng = random.Random(seed)
    rows = []
    for _ in range(iterations):
        shuffled = pnls[:]
        rng.shuffle(shuffled)
        total_pnl = sum(shuffled)
        max_dd = _max_drawdown_from_pnls(shuffled, start_balance)
        rows.append({
            "total_pnl": total_pnl,
            "max_dd": max_dd,
            "ending_balance": start_balance + total_pnl,
        })

    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> dict:
    return {
        "iterations": len(results),
        "pnl_p05": results["total_pnl"].quantile(0.05),
        "pnl_p50": results["total_pnl"].quantile(0.50),
        "pnl_p95": results["total_pnl"].quantile(0.95),
        "dd_p50": results["max_dd"].quantile(0.50),
        "dd_p95": results["max_dd"].quantile(0.95),
        "dd_max": results["max_dd"].max(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trades", default="backtest_results.csv")
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--out", default="monte_carlo_results.csv")
    args = parser.parse_args()

    trades = pd.read_csv(args.trades)
    results = run_monte_carlo(trades, iterations=args.iterations)
    summary = summarize(results)

    print("\n=== MONTE CARLO TRADE-SHUFFLE ===")
    print(f"Iterations : {summary['iterations']}")
    print(f"PnL p05    : {summary['pnl_p05']:.2f} USDT")
    print(f"PnL median : {summary['pnl_p50']:.2f} USDT")
    print(f"PnL p95    : {summary['pnl_p95']:.2f} USDT")
    print(f"DD median  : {summary['dd_p50']:.2f} USDT")
    print(f"DD p95     : {summary['dd_p95']:.2f} USDT")
    print(f"DD max     : {summary['dd_max']:.2f} USDT")

    results.to_csv(args.out, index=False)
    print(f"\nDetaylar: {args.out}")
