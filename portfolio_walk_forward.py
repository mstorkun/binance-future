"""
Portfolio walk-forward validation.

Uses the corrected portfolio engine: one wallet, shared capital, concurrent
position limits, funding/slippage/commission, calendar risk, and execution
guards.
"""
from __future__ import annotations

import math

import pandas as pd

import config
from portfolio_backtest import fetch_all_data, run_portfolio_backtest
from risk_profile_sweep import PROFILES


FIXED_PROFILE = "growth_70_compound"


def _profile_by_name(name: str) -> dict:
    for profile in PROFILES:
        if profile["name"] == name:
            return profile
    raise ValueError(f"Unknown profile: {name}")


def _slice_data(data_by_symbol: dict[str, dict], symbols: list[str], start_ts, end_ts) -> dict[str, dict]:
    out = {}
    for sym in symbols:
        df = data_by_symbol[sym]["df"]
        funding = data_by_symbol[sym].get("funding")
        out[sym] = {
            "df": df.loc[(df.index >= start_ts) & (df.index <= end_ts)].copy(),
            "funding": funding.loc[(funding.index >= start_ts) & (funding.index <= end_ts)].copy()
            if funding is not None and not funding.empty else funding,
        }
    return out


def _metrics(trades: pd.DataFrame, equity: pd.DataFrame, start_balance: float, bars: int) -> dict:
    if equity.empty:
        return {
            "trades": 0, "win_rate": 0.0, "return_pct": 0.0, "cagr_pct": 0.0,
            "max_dd_pct": 0.0, "final_equity": start_balance,
        }

    final = float(equity["equity"].iloc[-1])
    ret = (final - start_balance) / start_balance * 100
    years = max(bars * 4 / (24 * 365), 1 / 365)
    cagr = ((final / start_balance) ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity["equity"].cummax()
    max_dd = float((peak - equity["equity"]).max())
    max_dd_peak_pct = float(((peak - equity["equity"]) / peak.where(peak != 0)).max() * 100)
    win_rate = float((trades["pnl"] > 0).sum() / len(trades) * 100) if not trades.empty else 0.0
    return {
        "trades": len(trades),
        "win_rate": win_rate,
        "return_pct": ret,
        "cagr_pct": cagr,
        "max_dd_pct": max_dd / start_balance * 100,
        "max_dd_peak_pct": max_dd_peak_pct,
        "final_equity": final,
    }


def _score(row: dict) -> float:
    dd = max(row["max_dd_pct"], 1.0)
    return row["return_pct"] / dd


def run_walk_forward(
    years: int = 3,
    train_bars: int = 3000,
    test_bars: int = 500,
    roll_bars: int = 500,
    fixed_profile: str = FIXED_PROFILE,
) -> pd.DataFrame:
    symbols = config.SYMBOLS
    data = fetch_all_data(symbols, years=years)
    base_index = data[symbols[0]]["df"].index
    fixed = _profile_by_name(fixed_profile)

    rows = []
    period = 1
    start = 0
    while start + train_bars + test_bars <= len(base_index):
        train_start = base_index[start]
        train_end = base_index[start + train_bars - 1]
        test_start = base_index[start + train_bars]
        test_end = base_index[start + train_bars + test_bars - 1]

        train_data = _slice_data(data, symbols, train_start, train_end)
        test_data = _slice_data(data, symbols, test_start, test_end)

        train_rows = []
        for profile in PROFILES:
            trades, equity = run_portfolio_backtest(
                symbols,
                train_data,
                start_balance=config.CAPITAL_USDT,
                max_concurrent=profile["max_concurrent"],
                risk_per_trade=profile["risk_per_trade"],
                leverage=profile["leverage"],
                risk_basis=profile.get("risk_basis", config.RISK_BASIS),
            )
            m = _metrics(trades, equity, config.CAPITAL_USDT, train_bars)
            train_rows.append({**profile, **m, "score": _score(m)})

        best = max(train_rows, key=lambda r: r["score"] if math.isfinite(r["score"]) else -999)

        best_trades, best_equity = run_portfolio_backtest(
            symbols,
            test_data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=best["max_concurrent"],
            risk_per_trade=best["risk_per_trade"],
            leverage=best["leverage"],
            risk_basis=best.get("risk_basis", config.RISK_BASIS),
        )
        fixed_trades, fixed_equity = run_portfolio_backtest(
            symbols,
            test_data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=fixed["max_concurrent"],
            risk_per_trade=fixed["risk_per_trade"],
            leverage=fixed["leverage"],
            risk_basis=fixed.get("risk_basis", config.RISK_BASIS),
        )

        best_test = _metrics(best_trades, best_equity, config.CAPITAL_USDT, test_bars)
        fixed_test = _metrics(fixed_trades, fixed_equity, config.CAPITAL_USDT, test_bars)
        rows.append({
            "period": period,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "selected_profile": best["name"],
            "selected_train_return_pct": best["return_pct"],
            "selected_train_max_dd_pct": best["max_dd_pct"],
            **{f"selected_test_{k}": v for k, v in best_test.items()},
            "fixed_profile": fixed["name"],
            **{f"fixed_test_{k}": v for k, v in fixed_test.items()},
        })

        period += 1
        start += roll_bars

    results = pd.DataFrame(rows)
    results.to_csv("portfolio_walk_forward_results.csv", index=False)
    return results


if __name__ == "__main__":
    df = run_walk_forward()
    if df.empty:
        print("No walk-forward periods completed.")
        raise SystemExit(1)

    print("\n=== PORTFOLIO WALK-FORWARD ===")
    cols = [
        "period", "selected_profile", "selected_test_return_pct",
        "selected_test_max_dd_peak_pct", "fixed_profile", "fixed_test_return_pct",
        "fixed_test_max_dd_peak_pct", "fixed_test_trades",
    ]
    print(df[cols].to_string(index=False))
    print("\nSelected profile positive periods:",
          int((df["selected_test_return_pct"] > 0).sum()), "/", len(df))
    print("Growth fixed positive periods:",
          int((df["fixed_test_return_pct"] > 0).sum()), "/", len(df))
    print("Growth fixed avg return:",
          f"{df['fixed_test_return_pct'].mean():.2f}%")
    print("Growth fixed worst DD:",
          f"{df['fixed_test_max_dd_peak_pct'].max():.2f}%")
    print("\nOutput: portfolio_walk_forward_results.csv")
