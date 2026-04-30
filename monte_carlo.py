"""
Monte Carlo risk testleri — 3 mod:
  shuffle   - permutasyon (DD dagilimi, PnL invariant)
  bootstrap - replacement ile sample (PnL CI, IID varsayim)
  block     - block-bootstrap (trade-streak yapisini korur)
"""
from __future__ import annotations

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


def _record(s: list[float], start_balance: float) -> dict:
    return {
        "total_pnl": sum(s),
        "max_dd":    _max_drawdown_from_pnls(s, start_balance),
        "ending":    start_balance + sum(s),
    }


def shuffle_simulate(pnls, iterations, start_balance, seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(iterations):
        s = pnls[:]
        rng.shuffle(s)
        rows.append(_record(s, start_balance))
    return pd.DataFrame(rows)


def bootstrap_simulate(pnls, iterations, start_balance, seed):
    rng = random.Random(seed)
    n = len(pnls)
    rows = []
    for _ in range(iterations):
        s = [rng.choice(pnls) for _ in range(n)]
        rows.append(_record(s, start_balance))
    return pd.DataFrame(rows)


def block_bootstrap_simulate(pnls, iterations, start_balance, seed, block_size=5):
    rng = random.Random(seed)
    n = len(pnls)
    n_blocks = max(1, (n + block_size - 1) // block_size)
    rows = []
    for _ in range(iterations):
        s = []
        for _ in range(n_blocks):
            start = rng.randrange(0, max(1, n - block_size + 1))
            s.extend(pnls[start:start + block_size])
        s = s[:n]
        rows.append(_record(s, start_balance))
    return pd.DataFrame(rows)


def summarize(name: str, df: pd.DataFrame) -> dict:
    return {
        "method":  name,
        "iters":   len(df),
        "pnl_p05": df["total_pnl"].quantile(0.05),
        "pnl_p50": df["total_pnl"].quantile(0.50),
        "pnl_p95": df["total_pnl"].quantile(0.95),
        "dd_p50":  df["max_dd"].quantile(0.50),
        "dd_p95":  df["max_dd"].quantile(0.95),
        "dd_max":  df["max_dd"].max(),
        "pos_pct": (df["total_pnl"] > 0).sum() / len(df) * 100,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--trades", default="backtest_results.csv")
    p.add_argument("--iterations", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--block", type=int, default=5)
    p.add_argument("--method", choices=["shuffle", "bootstrap", "block", "all"], default="all")
    p.add_argument("--out", default="monte_carlo_results.csv")
    args = p.parse_args()

    trades = pd.read_csv(args.trades)
    if "pnl" not in trades.columns:
        raise ValueError("CSV icinde 'pnl' kolonu olmali.")
    pnls = [float(x) for x in trades["pnl"].dropna().tolist()]
    if not pnls:
        raise ValueError("PnL verisi yok.")

    start = config.CAPITAL_USDT
    summaries = []

    if args.method in ("shuffle", "all"):
        df = shuffle_simulate(pnls, args.iterations, start, args.seed)
        summaries.append(summarize("shuffle", df))
        df.to_csv(args.out.replace(".csv", "_shuffle.csv"), index=False)

    if args.method in ("bootstrap", "all"):
        df = bootstrap_simulate(pnls, args.iterations, start, args.seed)
        summaries.append(summarize("bootstrap", df))
        df.to_csv(args.out.replace(".csv", "_bootstrap.csv"), index=False)

    if args.method in ("block", "all"):
        df = block_bootstrap_simulate(pnls, args.iterations, start, args.seed, args.block)
        summaries.append(summarize(f"block(b={args.block})", df))
        df.to_csv(args.out.replace(".csv", "_block.csv"), index=False)

    sdf = pd.DataFrame(summaries)
    print("\n=== MONTE CARLO ===")
    print(sdf.to_string(index=False))
    sdf.to_csv("monte_carlo_summary.csv", index=False)
    print("\nOzet: monte_carlo_summary.csv")
