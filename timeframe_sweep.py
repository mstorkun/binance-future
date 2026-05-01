"""
Compare portfolio behavior across base timeframes.

This is a research tool. It temporarily overrides config.TIMEFRAME in memory,
keeps the strategy/risk profile unchanged, and compares full backtest,
calendar-normalized walk-forward, and Monte Carlo summaries.
"""
from __future__ import annotations

import argparse
import contextlib
import random
import re
from dataclasses import dataclass
from typing import Iterator

import pandas as pd

import config
import portfolio_backtest as pb
from risk_profile_sweep import PROFILES


DEFAULT_TIMEFRAMES = ["1h", "2h", "4h"]
DEFAULT_PROFILE = "growth_70_compound"
TRAIN_DAYS = 500
TEST_DAYS = 83
ROLL_DAYS = 83
SCALABLE_PERIOD_FIELDS = [
    "EMA_FAST",
    "EMA_SLOW",
    "ADX_PERIOD",
    "RSI_PERIOD",
    "ATR_PERIOD",
    "DONCHIAN_PERIOD",
    "DONCHIAN_EXIT",
    "VOLUME_MA_PERIOD",
    "VOLUME_PROFILE_LOOKBACK",
    "VOLUME_PROFILE_MIN_BARS",
    "PATTERN_SWEEP_LOOKBACK",
]


@dataclass(frozen=True)
class TimeframeResult:
    timeframe: str
    trades: int
    win_rate_pct: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float
    peak_dd_pct: float
    profit_factor: float | None
    commission: float
    slippage: float
    funding: float
    wf_periods: int
    wf_positive: int
    wf_avg_return_pct: float
    wf_worst_return_pct: float
    wf_worst_peak_dd_pct: float
    wf_total_trades: int
    mc_block_ending_p05: float | None
    mc_block_ending_p50: float | None
    mc_block_ending_p95: float | None
    mc_block_loss_prob_pct: float | None
    mc_block_peak_dd_p95_pct: float | None
    mc_block_peak_dd_max_pct: float | None


def timeframe_to_timedelta(timeframe: str) -> pd.Timedelta:
    match = re.fullmatch(r"(\d+)([mhdw])", timeframe.strip().lower())
    if not match:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return pd.Timedelta(minutes=value)
    if unit == "h":
        return pd.Timedelta(hours=value)
    if unit == "d":
        return pd.Timedelta(days=value)
    if unit == "w":
        return pd.Timedelta(weeks=value)
    raise ValueError(timeframe)


def bars_for_days(timeframe: str, days: int) -> int:
    seconds = timeframe_to_timedelta(timeframe).total_seconds()
    return max(1, int(round(days * 24 * 60 * 60 / seconds)))


def scale_factor_to_4h(timeframe: str) -> float:
    return pd.Timedelta(hours=4).total_seconds() / timeframe_to_timedelta(timeframe).total_seconds()


@contextlib.contextmanager
def temporary_timeframe(timeframe: str) -> Iterator[None]:
    saved_timeframe = config.TIMEFRAME
    saved_flow_period = getattr(config, "FLOW_PERIOD", saved_timeframe)
    try:
        config.TIMEFRAME = timeframe
        config.FLOW_PERIOD = timeframe
        yield
    finally:
        config.TIMEFRAME = saved_timeframe
        config.FLOW_PERIOD = saved_flow_period


@contextlib.contextmanager
def temporary_scaled_periods(timeframe: str, enabled: bool) -> Iterator[None]:
    saved = {field: getattr(config, field) for field in SCALABLE_PERIOD_FIELDS if hasattr(config, field)}
    try:
        if enabled:
            factor = scale_factor_to_4h(timeframe)
            for field, value in saved.items():
                setattr(config, field, max(2, int(round(float(value) * factor))))
        yield
    finally:
        for field, value in saved.items():
            setattr(config, field, value)


def profile_by_name(name: str) -> dict:
    for profile in PROFILES:
        if profile["name"] == name:
            return profile
    raise ValueError(f"Unknown profile: {name}")


def elapsed_years(equity: pd.DataFrame, fallback_years: float) -> float:
    if equity.empty or "timestamp" not in equity.columns:
        return fallback_years
    start = pd.Timestamp(equity["timestamp"].iloc[0])
    end = pd.Timestamp(equity["timestamp"].iloc[-1])
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    return max(days / 365.0, 1.0 / 365.0)


def summarize_backtest(
    timeframe: str,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    fallback_years: float,
) -> dict:
    start = config.CAPITAL_USDT
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else start
    years = elapsed_years(equity, fallback_years)
    total_return = (final_equity - start) / start * 100.0
    cagr = ((final_equity / start) ** (1 / years) - 1) * 100.0 if final_equity > 0 else -100.0
    if equity.empty:
        peak_dd_pct = 0.0
    else:
        peak = equity["equity"].cummax()
        peak_dd_pct = float(((peak - equity["equity"]) / peak.replace(0, pd.NA)).max() * 100)

    trade_count = int(len(trades))
    wins = int((trades["pnl"] > 0).sum()) if not trades.empty else 0
    win_rate = wins / trade_count * 100.0 if trade_count else 0.0
    profit_factor = None
    if not trades.empty:
        gross_win = float(trades.loc[trades["pnl"] > 0, "pnl"].sum())
        gross_loss = abs(float(trades.loc[trades["pnl"] <= 0, "pnl"].sum()))
        profit_factor = gross_win / gross_loss if gross_loss > 0 else None

    return {
        "timeframe": timeframe,
        "trades": trade_count,
        "win_rate_pct": round(win_rate, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return, 2),
        "cagr_pct": round(cagr, 2),
        "peak_dd_pct": round(peak_dd_pct, 2),
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "commission": round(float(trades["commission"].sum()), 2) if not trades.empty else 0.0,
        "slippage": round(float(trades["slippage"].sum()), 2) if not trades.empty else 0.0,
        "funding": round(float(trades["funding"].sum()), 2) if not trades.empty else 0.0,
    }


def slice_data(data_by_symbol: dict[str, dict], symbols: list[str], start_ts, end_ts) -> dict[str, dict]:
    out = {}
    for sym in symbols:
        df = data_by_symbol[sym]["df"]
        funding = data_by_symbol[sym].get("funding")
        out[sym] = {
            "df": df.loc[(df.index >= start_ts) & (df.index <= end_ts)].copy(),
            "funding": (
                funding.loc[(funding.index >= start_ts) & (funding.index <= end_ts)].copy()
                if funding is not None and not funding.empty else funding
            ),
        }
    return out


def walk_forward_fixed(
    timeframe: str,
    symbols: list[str],
    data: dict[str, dict],
    profile: dict,
    *,
    train_days: int = TRAIN_DAYS,
    test_days: int = TEST_DAYS,
    roll_days: int = ROLL_DAYS,
) -> pd.DataFrame:
    base_index = data[symbols[0]]["df"].index
    train_bars = bars_for_days(timeframe, train_days)
    test_bars = bars_for_days(timeframe, test_days)
    roll_bars = bars_for_days(timeframe, roll_days)

    rows = []
    period = 1
    start = 0
    while start + train_bars + test_bars <= len(base_index):
        train_start = base_index[start]
        train_end = base_index[start + train_bars - 1]
        test_start = base_index[start + train_bars]
        test_end = base_index[start + train_bars + test_bars - 1]
        test_data = slice_data(data, symbols, test_start, test_end)
        trades, equity = pb.run_portfolio_backtest(
            symbols,
            test_data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=profile["max_concurrent"],
            risk_per_trade=profile["risk_per_trade"],
            leverage=profile["leverage"],
            risk_basis=profile.get("risk_basis", config.RISK_BASIS),
        )
        summary = summarize_backtest(timeframe, trades, equity, fallback_years=test_days / 365.0)
        rows.append({
            "timeframe": timeframe,
            "period": period,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "train_bars": train_bars,
            "test_bars": test_bars,
            "roll_bars": roll_bars,
            "test_trades": summary["trades"],
            "test_return_pct": summary["total_return_pct"],
            "test_cagr_pct": summary["cagr_pct"],
            "test_peak_dd_pct": summary["peak_dd_pct"],
            "test_final_equity": summary["final_equity"],
        })
        period += 1
        start += roll_bars
    return pd.DataFrame(rows)


def equity_stats(returns: list[float], start_balance: float) -> dict:
    balance = start_balance
    peak = start_balance
    max_dd = 0.0
    max_dd_peak_pct = 0.0
    for ret in returns:
        balance *= 1.0 + ret
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
        if peak > 0:
            max_dd_peak_pct = max(max_dd_peak_pct, (peak - balance) / peak * 100.0)
    return {
        "ending": balance,
        "total_pnl": balance - start_balance,
        "max_dd_pct": max_dd / start_balance * 100.0,
        "max_dd_peak_pct": max_dd_peak_pct,
    }


def block_monte_carlo(
    trades: pd.DataFrame,
    *,
    iterations: int,
    block_size: int,
    seed: int,
) -> dict:
    if trades.empty:
        return {}
    if "pnl_return_pct" in trades.columns:
        returns = [float(x) / 100.0 for x in trades["pnl_return_pct"].dropna().tolist()]
    else:
        returns = [float(x) / config.CAPITAL_USDT for x in trades["pnl"].dropna().tolist()]
    if not returns:
        return {}

    rng = random.Random(seed)
    n = len(returns)
    rows = []
    for _ in range(iterations):
        sample: list[float] = []
        blocks = max(1, (n + block_size - 1) // block_size)
        for _ in range(blocks):
            start = rng.randrange(0, max(1, n - block_size + 1))
            sample.extend(returns[start:start + block_size])
        rows.append(equity_stats(sample[:n], config.CAPITAL_USDT))
    sims = pd.DataFrame(rows)
    return {
        "mc_block_ending_p05": round(float(sims["ending"].quantile(0.05)), 2),
        "mc_block_ending_p50": round(float(sims["ending"].quantile(0.50)), 2),
        "mc_block_ending_p95": round(float(sims["ending"].quantile(0.95)), 2),
        "mc_block_loss_prob_pct": round(float((sims["total_pnl"] < 0).mean() * 100), 2),
        "mc_block_peak_dd_p95_pct": round(float(sims["max_dd_peak_pct"].quantile(0.95)), 2),
        "mc_block_peak_dd_max_pct": round(float(sims["max_dd_peak_pct"].max()), 2),
    }


def run_timeframe(
    timeframe: str,
    *,
    symbols: list[str],
    years: int,
    profile: dict,
    mc_iterations: int,
    block_size: int,
    seed: int,
    scaled_params: bool,
) -> tuple[dict, pd.DataFrame]:
    mode = "scaled" if scaled_params else "raw"
    print(f"\n=== TIMEFRAME {timeframe} ({mode}) ===", flush=True)
    with temporary_timeframe(timeframe), temporary_scaled_periods(timeframe, scaled_params):
        data = pb.fetch_all_data(symbols, years=years)
        trades, equity = pb.run_portfolio_backtest(
            symbols,
            data,
            start_balance=config.CAPITAL_USDT,
            max_concurrent=profile["max_concurrent"],
            risk_per_trade=profile["risk_per_trade"],
            leverage=profile["leverage"],
            risk_basis=profile.get("risk_basis", config.RISK_BASIS),
        )
        summary = summarize_backtest(timeframe, trades, equity, fallback_years=years)
        wf = walk_forward_fixed(timeframe, symbols, data, profile)
        if wf.empty:
            wf_summary = {
                "wf_periods": 0,
                "wf_positive": 0,
                "wf_avg_return_pct": 0.0,
                "wf_worst_return_pct": 0.0,
                "wf_worst_peak_dd_pct": 0.0,
                "wf_total_trades": 0,
            }
        else:
            wf_summary = {
                "wf_periods": int(len(wf)),
                "wf_positive": int((wf["test_return_pct"] > 0).sum()),
                "wf_avg_return_pct": round(float(wf["test_return_pct"].mean()), 2),
                "wf_worst_return_pct": round(float(wf["test_return_pct"].min()), 2),
                "wf_worst_peak_dd_pct": round(float(wf["test_peak_dd_pct"].max()), 2),
                "wf_total_trades": int(wf["test_trades"].sum()),
            }
        mc_summary = block_monte_carlo(
            trades,
            iterations=mc_iterations,
            block_size=block_size,
            seed=seed,
        )
    return {"param_mode": mode, **summary, **wf_summary, **mc_summary}, wf


def run_sweep(
    *,
    timeframes: list[str],
    symbols: list[str],
    years: int,
    profile_name: str,
    mc_iterations: int,
    block_size: int,
    seed: int,
    scaled_params: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    profile = profile_by_name(profile_name)
    rows = []
    wf_rows = []
    for timeframe in timeframes:
        row, wf = run_timeframe(
            timeframe,
            symbols=symbols,
            years=years,
            profile=profile,
            mc_iterations=mc_iterations,
            block_size=block_size,
            seed=seed,
            scaled_params=scaled_params,
        )
        rows.append(row)
        if not wf.empty:
            wf_rows.append(wf)
        print(
            f"{timeframe}: CAGR={row['cagr_pct']}% DD={row['peak_dd_pct']}% "
            f"WF={row['wf_positive']}/{row['wf_periods']}",
            flush=True,
        )
    results = pd.DataFrame(rows)
    if not results.empty:
        results = results.sort_values(["wf_positive", "cagr_pct", "peak_dd_pct"], ascending=[False, False, True])
    wf_results = pd.concat(wf_rows, ignore_index=True) if wf_rows else pd.DataFrame()
    return results, wf_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare 1h/2h/4h portfolio behavior.")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--timeframes", nargs="*", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--symbols", nargs="*", default=list(config.SYMBOLS))
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--mc-iterations", type=int, default=2000)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scaled-params",
        action="store_true",
        help="Scale indicator lookbacks so 1h/2h roughly preserve the current 4h time horizon.",
    )
    parser.add_argument("--out", default="timeframe_sweep_results.csv")
    parser.add_argument("--wf-out", default="timeframe_walk_forward_results.csv")
    args = parser.parse_args()

    results, wf_results = run_sweep(
        timeframes=args.timeframes,
        symbols=args.symbols,
        years=args.years,
        profile_name=args.profile,
        mc_iterations=args.mc_iterations,
        block_size=args.block_size,
        seed=args.seed,
        scaled_params=args.scaled_params,
    )

    print("\n=== TIMEFRAME SWEEP ===")
    if results.empty:
        print("Sonuc yok.")
    else:
        print(results.to_string(index=False))
        results.to_csv(args.out, index=False)
        print(f"\nYazildi: {args.out}")
    if not wf_results.empty:
        wf_results.to_csv(args.wf_out, index=False)
        print(f"Yazildi: {args.wf_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
