"""
Side-by-side validation for passive mature-bot add-ons.

Loads market data once, then compares the current baseline against optional
protections, exit ladder, pair universe filtering, and their combination. It
does not change defaults or place orders.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from typing import Iterator

import pandas as pd

import config
import pair_universe
import portfolio_backtest as pb


@contextmanager
def temporary_config(**overrides) -> Iterator[None]:
    old = {key: getattr(config, key) for key in overrides}
    try:
        for key, value in overrides.items():
            setattr(config, key, value)
        yield
    finally:
        for key, value in old.items():
            setattr(config, key, value)


def _summarize(name: str, symbols: list[str], trades: pd.DataFrame, equity: pd.DataFrame, years: int) -> dict:
    if trades.empty or equity.empty:
        return {
            "variant": name,
            "symbols": ",".join(symbols),
            "trades": 0,
            "win_rate_pct": 0.0,
            "final_equity": equity["equity"].iloc[-1] if not equity.empty else config.CAPITAL_USDT,
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "peak_dd_pct": 0.0,
            "commission": 0.0,
            "slippage": 0.0,
            "funding": 0.0,
        }
    final_eq = float(equity["equity"].iloc[-1])
    peak = equity["equity"].cummax()
    peak_dd_pct = float(((peak - equity["equity"]) / peak).max() * 100)
    total_return = (final_eq - config.CAPITAL_USDT) / config.CAPITAL_USDT * 100
    cagr = ((final_eq / config.CAPITAL_USDT) ** (1 / years) - 1) * 100
    return {
        "variant": name,
        "symbols": ",".join(symbols),
        "trades": int(len(trades)),
        "win_rate_pct": round(float((trades["pnl"] > 0).mean() * 100), 2),
        "final_equity": round(final_eq, 2),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "peak_dd_pct": round(peak_dd_pct, 2),
        "commission": round(float(trades["commission"].sum()), 2),
        "slippage": round(float(trades["slippage"].sum()), 2),
        "funding": round(float(trades["funding"].sum()), 2),
    }


def run_compare(symbols: list[str], years: int = 3) -> pd.DataFrame:
    print("Veri yukleniyor...")
    data = pb.fetch_all_data(symbols, years=years)
    universe_report = pair_universe.score_universe(symbols, data)
    print("\n=== PAIR UNIVERSE REPORT ===")
    print(universe_report.to_string(index=False))

    variants = [
        ("baseline", {}, {}),
        ("protections", {"PROTECTIONS_ENABLED": True}, {"enable_protections": True}),
        ("exit_ladder", {"EXIT_LADDER_ENABLED": True}, {"enable_exit_ladder": True}),
        ("pair_universe", {"PAIR_UNIVERSE_ENABLED": True}, {"enable_pair_universe": True}),
        (
            "all_addons",
            {"PROTECTIONS_ENABLED": True, "EXIT_LADDER_ENABLED": True, "PAIR_UNIVERSE_ENABLED": True},
            {"enable_protections": True, "enable_exit_ladder": True, "enable_pair_universe": True},
        ),
    ]

    rows = []
    for name, overrides, kwargs in variants:
        with temporary_config(**overrides):
            active_symbols = pair_universe.select_symbols(symbols, data) if kwargs.get("enable_pair_universe") else list(symbols)
            trades, equity = pb.run_portfolio_backtest(
                symbols,
                data,
                start_balance=config.CAPITAL_USDT,
                max_concurrent=config.MAX_OPEN_POSITIONS,
                **kwargs,
            )
        rows.append(_summarize(name, active_symbols, trades, equity, years))

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare mature-bot add-ons against baseline.")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--symbols", nargs="*", default=config.SYMBOLS)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    result = run_compare(args.symbols, years=args.years)
    print("\n=== MATURE BOT COMPARE ===")
    print(result.to_string(index=False))
    if args.out:
        result.to_csv(args.out, index=False)
        print(f"\nYazildi: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
