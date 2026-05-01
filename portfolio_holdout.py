"""
Final holdout validation for the portfolio parameter selector.

This is a research-only check. It selects params/profile on the pre-holdout
training range, then evaluates the selected candidate on the final untouched
holdout bars.
"""

from __future__ import annotations

import argparse
import math

import pandas as pd

import config
import portfolio_backtest as pb
from portfolio_param_walk_forward import (
    Candidate,
    generate_candidates,
    select_profiles,
    _run_candidate,
    _score,
    _slice_data,
)


def holdout_ranges(index: pd.Index, holdout_bars: int) -> dict:
    if holdout_bars <= 0:
        raise ValueError("holdout_bars must be positive")
    if len(index) <= holdout_bars:
        raise ValueError("not enough bars for requested holdout")
    return {
        "train_start": index[0],
        "train_end": index[-holdout_bars - 1],
        "holdout_start": index[-holdout_bars],
        "holdout_end": index[-1],
        "train_bars": len(index) - holdout_bars,
        "holdout_bars": holdout_bars,
    }


def run_holdout(
    *,
    years: int = 3,
    holdout_bars: int = 500,
    max_param_combos: int | None = None,
    min_train_trades: int = 20,
    profile_names: list[str] | None = None,
    risk_capped: bool = True,
    out: str = "portfolio_holdout_results.csv",
) -> pd.DataFrame:
    symbols = list(config.SYMBOLS)
    data = pb.fetch_all_data(symbols, years=years)
    base_index = data[symbols[0]]["df"].index
    ranges = holdout_ranges(base_index, holdout_bars)

    train_slice = _slice_data(data, symbols, ranges["train_start"], ranges["train_end"])
    holdout_slice = _slice_data(data, symbols, ranges["holdout_start"], ranges["holdout_end"])
    profiles = select_profiles(profile_names, risk_capped=risk_capped)
    candidates = generate_candidates(profiles=profiles, max_param_combos=max_param_combos)

    print(
        f"Train: {ranges['train_start']} -> {ranges['train_end']} ({ranges['train_bars']} bars)",
        flush=True,
    )
    print(
        f"Holdout: {ranges['holdout_start']} -> {ranges['holdout_end']} ({ranges['holdout_bars']} bars)",
        flush=True,
    )
    print(f"Candidates: {len(candidates)}", flush=True)

    train_rows = []
    for idx, candidate in enumerate(candidates, start=1):
        metrics = _run_candidate(symbols, train_slice, candidate, int(ranges["train_bars"]))
        score = _score(metrics, min_train_trades)
        train_rows.append({"candidate": candidate, "score": score, **metrics})
        if idx % 25 == 0:
            print(f"  train candidates: {idx}/{len(candidates)}", flush=True)

    best = max(train_rows, key=lambda row: row["score"] if math.isfinite(row["score"]) else -1_000_000.0)
    selected: Candidate = best["candidate"]
    holdout_metrics = _run_candidate(
        symbols,
        holdout_slice,
        selected,
        int(ranges["holdout_bars"]),
    )
    params = selected.params
    row = {
        **ranges,
        "selected_candidate": selected.name,
        "selected_profile": selected.profile["name"],
        "selected_donchian": params.donchian,
        "selected_donchian_exit": params.donchian_exit,
        "selected_volume_mult": params.volume_mult,
        "selected_sl_atr_mult": params.sl_atr_mult,
        "selector_mode": "risk_capped" if risk_capped else "custom_profiles" if profile_names else "all_profiles",
        "profile_universe": ",".join(profile["name"] for profile in profiles),
        "train_score": best["score"],
        **{f"train_{key}": value for key, value in best.items() if key not in {"candidate", "score"}},
        **{f"holdout_{key}": value for key, value in holdout_metrics.items()},
    }
    results = pd.DataFrame([row])
    if out:
        results.to_csv(out, index=False)
    print(
        f"Selected {selected.name} | "
        f"train_return={row['train_return_pct']:.2f}% | "
        f"holdout_return={row['holdout_return_pct']:.2f}% | "
        f"holdout_dd={row['holdout_max_dd_peak_pct']:.2f}% | "
        f"holdout_trades={row['holdout_trades']}",
        flush=True,
    )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Select on pre-holdout data and test final holdout bars.")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--holdout-bars", type=int, default=500)
    parser.add_argument("--max-param-combos", type=int, default=0)
    parser.add_argument("--min-train-trades", type=int, default=20)
    parser.add_argument("--all-profiles", action="store_true", help="Use all risk profiles instead of risk-capped profiles.")
    parser.add_argument("--profiles", nargs="*", default=None, help="Explicit profile names to include.")
    parser.add_argument("--out", default="portfolio_holdout_results.csv")
    args = parser.parse_args()

    results = run_holdout(
        years=args.years,
        holdout_bars=args.holdout_bars,
        max_param_combos=args.max_param_combos or None,
        min_train_trades=args.min_train_trades,
        profile_names=args.profiles,
        risk_capped=not args.all_profiles and not args.profiles,
        out=args.out,
    )
    print("\n=== PORTFOLIO HOLDOUT ===")
    cols = [
        "selected_profile",
        "selected_donchian",
        "selected_donchian_exit",
        "selected_volume_mult",
        "selected_sl_atr_mult",
        "holdout_return_pct",
        "holdout_max_dd_peak_pct",
        "holdout_trades",
    ]
    print(results[cols].to_string(index=False))
    print(f"\nOutput: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
