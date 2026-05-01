"""
Replay selected portfolio walk-forward folds under harsher cost assumptions.

This is a research-only stress test. It reads a walk-forward result CSV, replays
each out-of-sample fold with the already-selected params/profile, and varies
fees, slippage, and funding-cost assumptions.
"""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
from typing import Iterator

import pandas as pd

import config
import portfolio_backtest as pb
from portfolio_param_walk_forward import Candidate, StrategyParams, _run_candidate, _slice_data
from risk_profile_sweep import PROFILES


@dataclass(frozen=True)
class CostScenario:
    name: str
    fee_mult: float = 1.0
    slippage_mult: float = 1.0
    funding_cost_mult: float = 1.0


DEFAULT_SCENARIOS = [
    CostScenario("baseline", 1.0, 1.0, 1.0),
    CostScenario("slippage_2x", 1.0, 2.0, 1.0),
    CostScenario("slippage_3x", 1.0, 3.0, 1.0),
    CostScenario("funding_cost_2x", 1.0, 1.0, 2.0),
    CostScenario("fee_slippage_2x", 2.0, 2.0, 1.0),
    CostScenario("severe_costs", 2.0, 3.0, 2.0),
]


def adverse_funding_cost(cost: float, multiplier: float) -> float:
    if multiplier <= 0:
        raise ValueError("funding multiplier must be positive")
    if cost >= 0:
        return cost * multiplier
    return cost / multiplier


@contextlib.contextmanager
def temporary_cost_scenario(scenario: CostScenario) -> Iterator[None]:
    saved_fee = config.ROUND_TRIP_FEE_RATE
    saved_slippage = config.SLIPPAGE_RATE_ROUND_TRIP
    saved_funding_cost = pb._funding_cost

    def stressed_funding_cost(*args, **kwargs):
        return adverse_funding_cost(saved_funding_cost(*args, **kwargs), scenario.funding_cost_mult)

    config.ROUND_TRIP_FEE_RATE = saved_fee * scenario.fee_mult
    config.SLIPPAGE_RATE_ROUND_TRIP = saved_slippage * scenario.slippage_mult
    pb._funding_cost = stressed_funding_cost
    try:
        yield
    finally:
        config.ROUND_TRIP_FEE_RATE = saved_fee
        config.SLIPPAGE_RATE_ROUND_TRIP = saved_slippage
        pb._funding_cost = saved_funding_cost


def _profile_by_name(name: str) -> dict:
    for profile in PROFILES:
        if profile["name"] == name:
            return profile
    raise ValueError(f"Unknown profile: {name}")


def _row_candidate(row: pd.Series) -> Candidate:
    params = StrategyParams(
        donchian=int(row["selected_donchian"]),
        donchian_exit=int(row["selected_donchian_exit"]),
        volume_mult=float(row["selected_volume_mult"]),
        sl_atr_mult=float(row["selected_sl_atr_mult"]),
    )
    return Candidate(params=params, profile=_profile_by_name(str(row["selected_profile"])))


def load_walk_forward_rows(path: str) -> pd.DataFrame:
    rows = pd.read_csv(path)
    required = {
        "period",
        "test_start",
        "test_end",
        "selected_profile",
        "selected_donchian",
        "selected_donchian_exit",
        "selected_volume_mult",
        "selected_sl_atr_mult",
    }
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"Walk-forward CSV missing required columns: {', '.join(sorted(missing))}")
    return rows


def summarize_folds(folds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario, group in folds.groupby("scenario", sort=False):
        compounded = config.CAPITAL_USDT
        for ret in group["test_return_pct"]:
            compounded *= 1.0 + float(ret) / 100.0
        rows.append({
            "scenario": scenario,
            "periods": int(len(group)),
            "positive_periods": int((group["test_return_pct"] > 0).sum()),
            "avg_test_return_pct": round(float(group["test_return_pct"].mean()), 4),
            "worst_test_return_pct": round(float(group["test_return_pct"].min()), 4),
            "worst_peak_dd_pct": round(float(group["test_max_dd_peak_pct"].max()), 4),
            "total_trades": int(group["test_trades"].sum()),
            "compounded_oos_final_equity": round(compounded, 2),
            "compounded_oos_return_pct": round((compounded / config.CAPITAL_USDT - 1.0) * 100.0, 4),
            "fee_mult": float(group["fee_mult"].iloc[0]),
            "slippage_mult": float(group["slippage_mult"].iloc[0]),
            "funding_cost_mult": float(group["funding_cost_mult"].iloc[0]),
        })
    return pd.DataFrame(rows)


def run_cost_stress(
    *,
    wf_results: str = "portfolio_param_walk_forward_risk_capped_results.csv",
    years: int = 3,
    scenarios: list[CostScenario] | None = None,
    folds_out: str = "portfolio_cost_stress_folds.csv",
    summary_out: str = "portfolio_cost_stress_results.csv",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenarios = scenarios or DEFAULT_SCENARIOS
    wf = load_walk_forward_rows(wf_results)
    symbols = list(config.SYMBOLS)
    data = pb.fetch_all_data(symbols, years=years)

    fold_rows = []
    for scenario in scenarios:
        print(f"\n=== Scenario: {scenario.name} ===", flush=True)
        with temporary_cost_scenario(scenario):
            for _, row in wf.iterrows():
                test_start = pd.Timestamp(row["test_start"])
                test_end = pd.Timestamp(row["test_end"])
                test_slice = _slice_data(data, symbols, test_start, test_end)
                bars = max(len(test_slice[symbols[0]]["df"]), 1)
                metrics = _run_candidate(symbols, test_slice, _row_candidate(row), bars)
                fold_row = {
                    "scenario": scenario.name,
                    "period": int(row["period"]),
                    "test_start": test_start,
                    "test_end": test_end,
                    "selected_candidate": row.get("selected_candidate", ""),
                    "selected_profile": row["selected_profile"],
                    "selected_donchian": int(row["selected_donchian"]),
                    "selected_donchian_exit": int(row["selected_donchian_exit"]),
                    "selected_volume_mult": float(row["selected_volume_mult"]),
                    "selected_sl_atr_mult": float(row["selected_sl_atr_mult"]),
                    "fee_mult": scenario.fee_mult,
                    "slippage_mult": scenario.slippage_mult,
                    "funding_cost_mult": scenario.funding_cost_mult,
                    **{f"test_{key}": value for key, value in metrics.items()},
                }
                fold_rows.append(fold_row)
                print(
                    f"  period {int(row['period'])}: "
                    f"return={metrics['return_pct']:.2f}% dd={metrics['max_dd_peak_pct']:.2f}% "
                    f"trades={metrics['trades']}",
                    flush=True,
                )

    folds = pd.DataFrame(fold_rows)
    summary = summarize_folds(folds)
    if folds_out:
        folds.to_csv(folds_out, index=False)
    if summary_out:
        summary.to_csv(summary_out, index=False)
    return folds, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay selected WF folds under stressed costs.")
    parser.add_argument("--wf-results", default="portfolio_param_walk_forward_risk_capped_results.csv")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--folds-out", default="portfolio_cost_stress_folds.csv")
    parser.add_argument("--summary-out", default="portfolio_cost_stress_results.csv")
    args = parser.parse_args()

    _, summary = run_cost_stress(
        wf_results=args.wf_results,
        years=args.years,
        folds_out=args.folds_out,
        summary_out=args.summary_out,
    )
    print("\n=== PORTFOLIO COST STRESS ===")
    print(summary.to_string(index=False))
    print(f"\nOutput: {args.summary_out}, {args.folds_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
