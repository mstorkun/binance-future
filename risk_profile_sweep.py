"""
Compare portfolio risk profiles on the same prepared data.

The sweep changes only sizing/leverage assumptions; it does not mutate config.py.
Outputs:
  - risk_profile_results.csv
"""
from __future__ import annotations

import pandas as pd

import config
from portfolio_backtest import fetch_all_data, run_portfolio_backtest


PROFILES = [
    {"name": "conservative", "leverage": 3, "risk_per_trade": 0.02, "max_concurrent": 2},
    {"name": "balanced", "leverage": 5, "risk_per_trade": 0.03, "max_concurrent": 2},
    {"name": "aggressive", "leverage": 10, "risk_per_trade": 0.05, "max_concurrent": 2},
]


def _summarize(name: str, leverage: float, risk_per_trade: float, max_concurrent: int,
               trades: pd.DataFrame, equity: pd.DataFrame, years: int, symbol_count: int) -> dict:
    start = config.CAPITAL_USDT
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else start
    peak = equity["equity"].cummax() if not equity.empty else pd.Series([start])
    dd = peak - equity["equity"] if not equity.empty else pd.Series([0.0])
    max_dd = float(dd.max())
    total_pnl = float(trades["pnl"].sum()) if not trades.empty else 0.0
    win_rate = float((trades["pnl"] > 0).sum() / len(trades) * 100) if not trades.empty else 0.0
    return_pct = (final_equity - start) / start * 100
    cagr = ((final_equity / start) ** (1 / years) - 1) * 100 if final_equity > 0 else -100.0
    calmar = cagr / (max_dd / start * 100) if max_dd > 0 else float("inf")

    return {
        "profile": name,
        "leverage": leverage,
        "sleeve_risk_pct": risk_per_trade * 100,
        "first_trade_portfolio_risk_pct": risk_per_trade / symbol_count * 100,
        "max_concurrent": max_concurrent,
        "trades": len(trades),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "final_equity": final_equity,
        "return_pct": return_pct,
        "cagr_pct": cagr,
        "max_dd": max_dd,
        "max_dd_pct": max_dd / start * 100,
        "calmar": calmar,
        "commission": float(trades["commission"].sum()) if not trades.empty else 0.0,
        "slippage": float(trades["slippage"].sum()) if not trades.empty else 0.0,
        "funding": float(trades["funding"].sum()) if not trades.empty else 0.0,
    }


def run_sweep(years: int = 3) -> pd.DataFrame:
    symbols = config.SYMBOLS
    print(f"Loading data for {symbols}...")
    data = fetch_all_data(symbols, years=years)

    rows = []
    for profile in PROFILES:
        print(
            f"\n>>> {profile['name']}: "
            f"{profile['leverage']}x, risk={profile['risk_per_trade'] * 100:.1f}%"
        )
        trades, equity = run_portfolio_backtest(
            symbols,
            data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=profile["max_concurrent"],
            risk_per_trade=profile["risk_per_trade"],
            leverage=profile["leverage"],
        )
        rows.append(_summarize(
            profile["name"],
            profile["leverage"],
            profile["risk_per_trade"],
            profile["max_concurrent"],
            trades,
            equity,
            years,
            len(symbols),
        ))

    results = pd.DataFrame(rows)
    results.to_csv("risk_profile_results.csv", index=False)
    print("\n=== RISK PROFILE SWEEP ===")
    print(results.to_string(index=False))
    print("\nOutput: risk_profile_results.csv")
    return results


if __name__ == "__main__":
    run_sweep(years=3)
