"""
Portfolio Monte Carlo validation for a selected risk profile.

Runs the corrected portfolio backtest, then simulates trade-order uncertainty
with shuffle, bootstrap, and block-bootstrap methods.
"""
from __future__ import annotations

import argparse
import random

import pandas as pd

import config
from portfolio_backtest import fetch_all_data, run_portfolio_backtest
from risk_profile_sweep import PROFILES


def _profile_by_name(name: str) -> dict:
    for profile in PROFILES:
        if profile["name"] == name:
            return profile
    raise ValueError(f"Unknown profile: {name}")


def _equity_stats(pnls: list[float], start_balance: float) -> dict:
    balance = start_balance
    peak = start_balance
    max_dd = 0.0
    max_dd_peak_pct = 0.0
    min_balance = start_balance
    for pnl in pnls:
        balance += pnl
        peak = max(peak, balance)
        min_balance = min(min_balance, balance)
        max_dd = max(max_dd, peak - balance)
        if peak > 0:
            max_dd_peak_pct = max(max_dd_peak_pct, (peak - balance) / peak * 100)
    return {
        "ending": balance,
        "total_pnl": balance - start_balance,
        "max_dd": max_dd,
        "max_dd_pct": max_dd / start_balance * 100,
        "max_dd_peak_pct": max_dd_peak_pct,
        "min_balance": min_balance,
    }


def _simulate(pnls: list[float], method: str, iterations: int, block_size: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    n = len(pnls)
    rows = []
    for _ in range(iterations):
        if method == "shuffle":
            sample = pnls[:]
            rng.shuffle(sample)
        elif method == "bootstrap":
            sample = [rng.choice(pnls) for _ in range(n)]
        elif method == "block":
            sample = []
            blocks = max(1, (n + block_size - 1) // block_size)
            for _ in range(blocks):
                start = rng.randrange(0, max(1, n - block_size + 1))
                sample.extend(pnls[start:start + block_size])
            sample = sample[:n]
        else:
            raise ValueError(method)
        rows.append(_equity_stats(sample, config.CAPITAL_USDT))
    return pd.DataFrame(rows)


def _summary(method: str, df: pd.DataFrame) -> dict:
    return {
        "method": method,
        "iterations": len(df),
        "ending_p05": df["ending"].quantile(0.05),
        "ending_p50": df["ending"].quantile(0.50),
        "ending_p95": df["ending"].quantile(0.95),
        "pnl_p05": df["total_pnl"].quantile(0.05),
        "dd_p50_pct": df["max_dd_pct"].quantile(0.50),
        "dd_p95_pct": df["max_dd_pct"].quantile(0.95),
        "dd_max_pct": df["max_dd_pct"].max(),
        "peak_dd_p50_pct": df["max_dd_peak_pct"].quantile(0.50),
        "peak_dd_p95_pct": df["max_dd_peak_pct"].quantile(0.95),
        "peak_dd_max_pct": df["max_dd_peak_pct"].max(),
        "loss_prob_pct": (df["total_pnl"] < 0).mean() * 100,
        "dd_gt_30_pct": (df["max_dd_pct"] > 30).mean() * 100,
        "dd_gt_50_pct": (df["max_dd_pct"] > 50).mean() * 100,
    }


def run_profile(profile_name: str, years: int, iterations: int, block_size: int, seed: int) -> pd.DataFrame:
    profile = _profile_by_name(profile_name)
    symbols = config.SYMBOLS
    data = fetch_all_data(symbols, years=years)
    trades, equity = run_portfolio_backtest(
        symbols,
        data,
        start_balance=config.CAPITAL_USDT,
        max_concurrent=profile["max_concurrent"],
        risk_per_trade=profile["risk_per_trade"],
        leverage=profile["leverage"],
        risk_basis=profile.get("risk_basis", config.RISK_BASIS),
    )
    if trades.empty:
        raise ValueError("No trades for Monte Carlo.")

    trade_out = f"portfolio_trades_{profile_name}.csv"
    equity_out = f"portfolio_equity_{profile_name}.csv"
    trades.to_csv(trade_out, index=False)
    equity.to_csv(equity_out, index=False)

    pnls = [float(x) for x in trades["pnl"].dropna().tolist()]
    summaries = []
    for method in ("shuffle", "bootstrap", "block"):
        sims = _simulate(pnls, method, iterations, block_size, seed)
        sims.to_csv(f"portfolio_monte_carlo_{profile_name}_{method}.csv", index=False)
        summaries.append(_summary(method if method != "block" else f"block(b={block_size})", sims))

    summary = pd.DataFrame(summaries)
    summary.to_csv(f"portfolio_monte_carlo_{profile_name}_summary.csv", index=False)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="growth_70_compound")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out = run_profile(args.profile, args.years, args.iterations, args.block_size, args.seed)
    print("\n=== PORTFOLIO MONTE CARLO ===")
    print(out.to_string(index=False))
    print(f"\nOutput: portfolio_monte_carlo_{args.profile}_summary.csv")
