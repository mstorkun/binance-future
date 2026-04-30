"""
Portfolio candidate sweep.

This script keeps the main strategy unchanged and searches for better symbol
combinations. It fetches each candidate once, filters the universe with
pair_universe scoring, and runs the existing portfolio backtest for each combo.
"""

from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass

import pandas as pd

import config
import pair_universe
import portfolio_backtest as pb


DEFAULT_CANDIDATES = [
    "SOL/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "BTC/USDT",
    "XRP/USDT",
    "DOGE/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "LTC/USDT",
    "BCH/USDT",
    "NEAR/USDT",
    "APT/USDT",
    "SUI/USDT",
    "TRX/USDT",
]


@dataclass(frozen=True)
class SweepConfig:
    years: int
    min_size: int
    max_size: int
    top: int
    min_trades: int
    max_peak_dd_pct: float | None
    filter_universe: bool
    include_current: bool
    max_combos: int | None


def fetch_candidate_data(symbols: list[str], years: int) -> tuple[dict[str, dict], pd.DataFrame]:
    data: dict[str, dict] = {}
    skipped = []
    for symbol in symbols:
        try:
            print(f"\n--- Veri: {symbol} ---", flush=True)
            data.update(pb.fetch_all_data([symbol], years=years))
        except Exception as exc:
            skipped.append({"symbol": symbol, "reason": f"{type(exc).__name__}: {exc}"})
            print(f"SKIP {symbol}: {type(exc).__name__}: {exc}", flush=True)
    return data, pd.DataFrame(skipped)


def generate_combos(
    symbols: list[str],
    *,
    min_size: int,
    max_size: int,
    include_current: bool = True,
    max_combos: int | None = None,
) -> list[tuple[str, ...]]:
    symbols = list(dict.fromkeys(symbols))
    min_size = max(1, min_size)
    max_size = min(max_size, len(symbols))
    combos: list[tuple[str, ...]] = []
    for size in range(min_size, max_size + 1):
        combos.extend(itertools.combinations(symbols, size))

    if include_current:
        current = tuple(sym for sym in config.SYMBOLS if sym in symbols)
        if current and min_size <= len(current) <= max_size and current not in combos:
            combos.insert(0, current)

    if max_combos is not None and max_combos > 0:
        combos = combos[:max_combos]
    return combos


def summarize_combo(
    symbols: tuple[str, ...],
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    years: int,
) -> dict:
    if equity.empty:
        final_eq = config.CAPITAL_USDT
        peak_dd_pct = 0.0
    else:
        final_eq = float(equity["equity"].iloc[-1])
        peak = equity["equity"].cummax()
        peak_dd_pct = float(((peak - equity["equity"]) / peak).max() * 100)

    trades_count = int(len(trades))
    wins = int((trades["pnl"] > 0).sum()) if not trades.empty else 0
    win_rate = (wins / trades_count * 100) if trades_count else 0.0
    total_return = (final_eq - config.CAPITAL_USDT) / config.CAPITAL_USDT * 100
    cagr = ((final_eq / config.CAPITAL_USDT) ** (1 / years) - 1) * 100 if final_eq > 0 else -100.0
    profit_factor = None
    if not trades.empty:
        gross_win = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
        gross_loss = abs(float(trades.loc[trades["pnl"] <= 0, "pnl"].sum()))
        profit_factor = gross_win / gross_loss if gross_loss > 0 else None

    return {
        "symbols": ",".join(symbols),
        "symbol_count": len(symbols),
        "trades": trades_count,
        "win_rate_pct": round(win_rate, 2),
        "final_equity": round(final_eq, 2),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "peak_dd_pct": round(peak_dd_pct, 2),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else "",
        "commission": round(float(trades["commission"].sum()), 2) if not trades.empty else 0.0,
        "slippage": round(float(trades["slippage"].sum()), 2) if not trades.empty else 0.0,
        "funding": round(float(trades["funding"].sum()), 2) if not trades.empty else 0.0,
    }


def run_sweep(candidates: list[str], sweep: SweepConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = list(dict.fromkeys(candidates))
    data, skipped = fetch_candidate_data(candidates, sweep.years)
    available = [symbol for symbol in candidates if symbol in data]
    universe = pair_universe.score_universe(available, data) if available else pd.DataFrame()
    if sweep.filter_universe and not universe.empty:
        active_symbols = universe.loc[universe["tradable"], "symbol"].tolist()
    else:
        active_symbols = available

    combos = generate_combos(
        active_symbols,
        min_size=sweep.min_size,
        max_size=sweep.max_size,
        include_current=sweep.include_current,
        max_combos=sweep.max_combos,
    )
    print(f"\nBacktest edilecek kombinasyon: {len(combos)}", flush=True)

    rows = []
    for index, combo in enumerate(combos, start=1):
        print(f"[{index}/{len(combos)}] {', '.join(combo)}", flush=True)
        trades, equity = pb.run_portfolio_backtest(
            list(combo),
            data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=min(config.MAX_OPEN_POSITIONS, len(combo)),
        )
        row = summarize_combo(combo, trades, equity, sweep.years)
        if row["trades"] < sweep.min_trades:
            row["filtered_reason"] = "min_trades"
        elif sweep.max_peak_dd_pct is not None and row["peak_dd_pct"] > sweep.max_peak_dd_pct:
            row["filtered_reason"] = "max_dd"
        else:
            row["filtered_reason"] = ""
        rows.append(row)

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["filtered_reason", "cagr_pct", "peak_dd_pct", "trades"],
            ascending=[True, False, True, False],
        )
    return result, universe, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Sweep symbol combinations without changing the strategy.")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_CANDIDATES)
    parser.add_argument("--min-size", type=int, default=3)
    parser.add_argument("--max-size", type=int, default=5)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--min-trades", type=int, default=50)
    parser.add_argument("--max-peak-dd-pct", type=float, default=15.0)
    parser.add_argument("--no-universe-filter", action="store_true")
    parser.add_argument("--no-current", action="store_true")
    parser.add_argument("--max-combos", type=int, default=0)
    parser.add_argument("--out", default="portfolio_candidate_sweep_results.csv")
    parser.add_argument("--universe-out", default="portfolio_candidate_universe.csv")
    args = parser.parse_args()

    sweep = SweepConfig(
        years=args.years,
        min_size=args.min_size,
        max_size=args.max_size,
        top=args.top,
        min_trades=args.min_trades,
        max_peak_dd_pct=args.max_peak_dd_pct,
        filter_universe=not args.no_universe_filter,
        include_current=not args.no_current,
        max_combos=args.max_combos or None,
    )
    results, universe, skipped = run_sweep(args.symbols, sweep)

    if not universe.empty:
        print("\n=== UNIVERSE ===")
        print(universe.to_string(index=False))
        if args.universe_out:
            universe.to_csv(args.universe_out, index=False)
    if not skipped.empty:
        print("\n=== SKIPPED ===")
        print(skipped.to_string(index=False))

    print("\n=== TOP CANDIDATES ===")
    if results.empty:
        print("Sonuc yok.")
    else:
        print(results.head(args.top).to_string(index=False))
        if args.out:
            results.to_csv(args.out, index=False)
            print(f"\nYazildi: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
