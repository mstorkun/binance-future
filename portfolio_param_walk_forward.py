"""
Portfolio walk-forward with train-only strategy parameter selection.

This is a research tool. It does not change config.py on disk and it does not
place orders. Each fold selects Donchian/volume/stop parameters and a risk
profile on the train window, then applies only that selected candidate to the
out-of-sample test window.
"""

from __future__ import annotations

import argparse
import contextlib
import math
from dataclasses import dataclass
from typing import Iterator

import pandas as pd

import config
from portfolio_backtest import fetch_all_data, run_portfolio_backtest
from risk_profile_sweep import PROFILES


DEFAULT_PARAM_GRID = {
    "donchian": [15, 20, 30],
    "donchian_exit": [8, 10, 15],
    "volume_mult": [1.2, 1.5, 2.0],
    "sl_atr_mult": [1.5, 2.0, 2.5],
}

RISK_CAPPED_PROFILE_NAMES = ("conservative", "balanced", "growth_70_compound")


@dataclass(frozen=True)
class StrategyParams:
    donchian: int
    donchian_exit: int
    volume_mult: float
    sl_atr_mult: float


@dataclass(frozen=True)
class Candidate:
    params: StrategyParams
    profile: dict

    @property
    def name(self) -> str:
        p = self.params
        return (
            f"{self.profile['name']}|D{p.donchian}|DX{p.donchian_exit}|"
            f"VOL{p.volume_mult}|SL{p.sl_atr_mult}"
        )


@contextlib.contextmanager
def temporary_strategy_params(params: StrategyParams) -> Iterator[None]:
    saved = (
        config.DONCHIAN_PERIOD,
        config.DONCHIAN_EXIT,
        config.VOLUME_MULT,
        config.SL_ATR_MULT,
    )
    config.DONCHIAN_PERIOD = params.donchian
    config.DONCHIAN_EXIT = params.donchian_exit
    config.VOLUME_MULT = params.volume_mult
    config.SL_ATR_MULT = params.sl_atr_mult
    try:
        yield
    finally:
        (
            config.DONCHIAN_PERIOD,
            config.DONCHIAN_EXIT,
            config.VOLUME_MULT,
            config.SL_ATR_MULT,
        ) = saved


def generate_param_grid(max_combos: int | None = None) -> list[StrategyParams]:
    rows: list[StrategyParams] = []
    for donchian in DEFAULT_PARAM_GRID["donchian"]:
        for donchian_exit in DEFAULT_PARAM_GRID["donchian_exit"]:
            if donchian_exit >= donchian:
                continue
            for volume_mult in DEFAULT_PARAM_GRID["volume_mult"]:
                for sl_atr_mult in DEFAULT_PARAM_GRID["sl_atr_mult"]:
                    rows.append(StrategyParams(donchian, donchian_exit, volume_mult, sl_atr_mult))
    if max_combos is not None and max_combos > 0:
        rows = rows[:max_combos]
    return rows


def generate_candidates(
    *,
    profiles: list[dict] | None = None,
    max_param_combos: int | None = None,
) -> list[Candidate]:
    profiles = profiles or PROFILES
    return [
        Candidate(params=params, profile=profile)
        for params in generate_param_grid(max_param_combos)
        for profile in profiles
    ]


def select_profiles(profile_names: list[str] | None = None, *, risk_capped: bool = False) -> list[dict]:
    if profile_names:
        allowed = set(profile_names)
    elif risk_capped:
        allowed = set(RISK_CAPPED_PROFILE_NAMES)
    else:
        allowed = {profile["name"] for profile in PROFILES}

    profiles = [profile for profile in PROFILES if profile["name"] in allowed]
    found = {profile["name"] for profile in profiles}
    missing = sorted(allowed - found)
    if missing:
        raise ValueError(f"Unknown profile name(s): {', '.join(missing)}")
    return profiles


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


def _apply_param_columns(data_by_symbol: dict[str, dict], params: StrategyParams) -> dict[str, dict]:
    out = {}
    for sym, payload in data_by_symbol.items():
        df = payload["df"].copy()
        df["donchian_high"] = df["high"].rolling(params.donchian).max().shift(1)
        df["donchian_low"] = df["low"].rolling(params.donchian).min().shift(1)
        df["donchian_exit_high"] = df["high"].rolling(params.donchian_exit).max().shift(1)
        df["donchian_exit_low"] = df["low"].rolling(params.donchian_exit).min().shift(1)
        out[sym] = {"df": df.dropna(), "funding": payload.get("funding")}
    return out


def _metrics(trades: pd.DataFrame, equity: pd.DataFrame, start_balance: float, bars: int) -> dict:
    if equity.empty:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "return_pct": 0.0,
            "cagr_pct": 0.0,
            "max_dd_pct": 0.0,
            "max_dd_peak_pct": 0.0,
            "final_equity": start_balance,
        }

    final = float(equity["equity"].iloc[-1])
    ret = (final - start_balance) / start_balance * 100
    years = max(bars * 4 / (24 * 365), 1 / 365)
    cagr = ((final / start_balance) ** (1 / years) - 1) * 100 if final > 0 else -100.0
    peak = equity["equity"].cummax()
    max_dd_pct = float(((peak - equity["equity"]) / peak.where(peak != 0)).max() * 100)
    win_rate = float((trades["pnl"] > 0).sum() / len(trades) * 100) if not trades.empty else 0.0
    return {
        "trades": int(len(trades)),
        "win_rate": win_rate,
        "return_pct": ret,
        "cagr_pct": cagr,
        "max_dd_pct": max_dd_pct,
        "max_dd_peak_pct": max_dd_pct,
        "final_equity": final,
    }


def _score(row: dict, min_trades: int) -> float:
    if row["trades"] < min_trades:
        return -1_000_000.0 + row["trades"]
    dd = max(float(row["max_dd_peak_pct"]), 1.0)
    return float(row["return_pct"]) / dd


def _run_candidate(
    symbols: list[str],
    data_slice: dict[str, dict],
    candidate: Candidate,
    bars: int,
) -> dict:
    data = _apply_param_columns(data_slice, candidate.params)
    profile = candidate.profile
    with temporary_strategy_params(candidate.params):
        trades, equity = run_portfolio_backtest(
            symbols,
            data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=min(int(profile["max_concurrent"]), len(symbols)),
            risk_per_trade=float(profile["risk_per_trade"]),
            leverage=float(profile["leverage"]),
            risk_basis=profile.get("risk_basis", config.RISK_BASIS),
        )
    return _metrics(trades, equity, config.CAPITAL_USDT, bars)


def run_walk_forward(
    *,
    years: int = 3,
    train_bars: int = 3000,
    test_bars: int = 500,
    roll_bars: int = 500,
    max_param_combos: int | None = None,
    min_train_trades: int = 20,
    profile_names: list[str] | None = None,
    risk_capped: bool = False,
    out: str = "portfolio_param_walk_forward_results.csv",
    matrix_out: str = "",
) -> pd.DataFrame:
    symbols = list(config.SYMBOLS)
    data = fetch_all_data(symbols, years=years)
    base_index = data[symbols[0]]["df"].index
    profiles = select_profiles(profile_names, risk_capped=risk_capped)
    candidates = generate_candidates(profiles=profiles, max_param_combos=max_param_combos)

    rows = []
    matrix_rows = []
    period = 1
    start = 0
    while start + train_bars + test_bars <= len(base_index):
        train_start = base_index[start]
        train_end = base_index[start + train_bars - 1]
        test_start = base_index[start + train_bars]
        test_end = base_index[start + train_bars + test_bars - 1]

        train_slice = _slice_data(data, symbols, train_start, train_end)
        test_slice = _slice_data(data, symbols, test_start, test_end)

        train_rows = []
        print(f"\n--- WF period {period} ---", flush=True)
        print(f"Train: {train_start} -> {train_end} | Test: {test_start} -> {test_end}", flush=True)
        for idx, candidate in enumerate(candidates, start=1):
            metrics = _run_candidate(symbols, train_slice, candidate, train_bars)
            score = _score(metrics, min_train_trades)
            train_rows.append({"candidate": candidate, "score": score, **metrics})
            if idx % 25 == 0:
                print(f"  train candidates: {idx}/{len(candidates)}", flush=True)

        best = max(train_rows, key=lambda row: row["score"] if math.isfinite(row["score"]) else -1_000_000.0)
        selected: Candidate = best["candidate"]
        matrix_test_metrics_by_name: dict[str, dict] = {}
        if matrix_out:
            for train_row in train_rows:
                candidate: Candidate = train_row["candidate"]
                candidate_test_metrics = _run_candidate(symbols, test_slice, candidate, test_bars)
                matrix_test_metrics_by_name[candidate.name] = candidate_test_metrics
                p = candidate.params
                matrix_rows.append({
                    "period": period,
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "candidate": candidate.name,
                    "selected": candidate.name == selected.name,
                    "profile": candidate.profile["name"],
                    "donchian": p.donchian,
                    "donchian_exit": p.donchian_exit,
                    "volume_mult": p.volume_mult,
                    "sl_atr_mult": p.sl_atr_mult,
                    "selector_mode": "risk_capped" if risk_capped else "custom_profiles" if profile_names else "all_profiles",
                    "profile_universe": ",".join(profile["name"] for profile in profiles),
                    "train_score": train_row["score"],
                    **{f"train_{k}": v for k, v in train_row.items() if k not in {"candidate", "score"}},
                    **{f"test_{k}": v for k, v in candidate_test_metrics.items()},
                })

        test_metrics = matrix_test_metrics_by_name.get(selected.name)
        if test_metrics is None:
            test_metrics = _run_candidate(symbols, test_slice, selected, test_bars)

        p = selected.params
        row = {
            "period": period,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "selected_candidate": selected.name,
            "selected_profile": selected.profile["name"],
            "selected_donchian": p.donchian,
            "selected_donchian_exit": p.donchian_exit,
            "selected_volume_mult": p.volume_mult,
            "selected_sl_atr_mult": p.sl_atr_mult,
            "selector_mode": "risk_capped" if risk_capped else "custom_profiles" if profile_names else "all_profiles",
            "profile_universe": ",".join(profile["name"] for profile in profiles),
            "train_score": best["score"],
            **{f"train_{k}": v for k, v in best.items() if k not in {"candidate", "score"}},
            **{f"test_{k}": v for k, v in test_metrics.items()},
        }
        rows.append(row)
        print(
            f"Selected {selected.name} | "
            f"train_return={row['train_return_pct']:.2f}% | "
            f"test_return={row['test_return_pct']:.2f}% | "
            f"test_dd={row['test_max_dd_peak_pct']:.2f}%",
            flush=True,
        )

        period += 1
        start += roll_bars

    results = pd.DataFrame(rows)
    if out:
        results.to_csv(out, index=False)
    if matrix_out:
        pd.DataFrame(matrix_rows).to_csv(matrix_out, index=False)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Portfolio walk-forward with train-only parameter selection.")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--train-bars", type=int, default=3000)
    parser.add_argument("--test-bars", type=int, default=500)
    parser.add_argument("--roll-bars", type=int, default=500)
    parser.add_argument("--max-param-combos", type=int, default=0, help="Limit parameter combos for a quick smoke run.")
    parser.add_argument("--min-train-trades", type=int, default=20)
    parser.add_argument(
        "--risk-capped",
        action="store_true",
        help="Select only conservative, balanced, and growth_70_compound profiles.",
    )
    parser.add_argument(
        "--profiles",
        nargs="*",
        default=None,
        help="Explicit profile names to include in selector universe.",
    )
    parser.add_argument("--out", default="portfolio_param_walk_forward_results.csv")
    parser.add_argument(
        "--matrix-out",
        default="",
        help="Optional candidate-by-fold matrix CSV for PBO-style analysis. Expensive: tests every candidate in every fold.",
    )
    args = parser.parse_args()

    results = run_walk_forward(
        years=args.years,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        roll_bars=args.roll_bars,
        max_param_combos=args.max_param_combos or None,
        min_train_trades=args.min_train_trades,
        profile_names=args.profiles,
        risk_capped=args.risk_capped,
        out=args.out,
        matrix_out=args.matrix_out,
    )
    if results.empty:
        print("No walk-forward periods completed.")
        return 1

    cols = [
        "period",
        "selected_profile",
        "selected_donchian",
        "selected_donchian_exit",
        "selected_volume_mult",
        "selected_sl_atr_mult",
        "train_return_pct",
        "test_return_pct",
        "test_max_dd_peak_pct",
        "test_trades",
    ]
    print("\n=== PORTFOLIO PARAM WALK-FORWARD ===")
    print(results[cols].to_string(index=False))
    print("\nPositive test periods:", int((results["test_return_pct"] > 0).sum()), "/", len(results))
    print("Average test return:", f"{results['test_return_pct'].mean():.2f}%")
    print("Worst test DD:", f"{results['test_max_dd_peak_pct'].max():.2f}%")
    print(f"\nOutput: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
