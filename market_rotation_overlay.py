from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

import market_rotation_report as rotation_report
from hurst_mtf_momentum_report import fetch_ohlcv_history, make_exchange, markdown_table


@dataclass(frozen=True)
class FoldSchedule:
    fold: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    bad_buckets: tuple[str, ...]


def _profit_factor(pnl: pd.Series) -> float | None:
    wins = float(pnl[pnl > 0].sum())
    losses = abs(float(pnl[pnl < 0].sum()))
    if losses == 0:
        return None
    return wins / losses


def _bucket_keys(row: pd.Series) -> tuple[str, str]:
    return (
        f"align:{row.get('rotation_alignment')}",
        f"side_regime:{row.get('side')}|{row.get('rotation_regime')}",
    )


def _learn_bad_buckets(
    train: pd.DataFrame,
    *,
    min_bucket_trades: int,
    max_profit_factor: float,
    max_mean_return_pct: float,
) -> tuple[str, ...]:
    bucket_rows: dict[str, list[int]] = {}
    for idx, row in train.iterrows():
        for key in _bucket_keys(row):
            bucket_rows.setdefault(key, []).append(idx)

    bad: list[str] = []
    for key, indexes in bucket_rows.items():
        frame = train.loc[indexes]
        if len(frame) < int(min_bucket_trades):
            continue
        pnl = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
        returns = pd.to_numeric(frame["pnl_return_pct"], errors="coerce").fillna(0.0)
        pf = _profit_factor(pnl)
        pf_value = float("inf") if pf is None and float(pnl.sum()) > 0.0 else (0.0 if pf is None else float(pf))
        if float(pnl.sum()) < 0.0 or pf_value <= float(max_profit_factor) or float(returns.mean()) <= float(max_mean_return_pct):
            bad.append(key)
    return tuple(sorted(set(bad)))


def build_fold_schedules(
    annotated: pd.DataFrame,
    *,
    train_trades: int = 120,
    test_trades: int = 40,
    roll_trades: int = 40,
    min_bucket_trades: int = 5,
    max_profit_factor: float = 1.0,
    max_mean_return_pct: float = 0.0,
) -> list[FoldSchedule]:
    ordered = annotated.sort_values("entry_time").reset_index(drop=True)
    schedules: list[FoldSchedule] = []
    start = 0
    fold = 1
    while start + train_trades + test_trades <= len(ordered):
        train = ordered.iloc[start:start + train_trades]
        test = ordered.iloc[start + train_trades:start + train_trades + test_trades]
        schedules.append(
            FoldSchedule(
                fold=fold,
                train_start=pd.Timestamp(train["entry_time"].iloc[0]),
                train_end=pd.Timestamp(train["entry_time"].iloc[-1]),
                test_start=pd.Timestamp(test["entry_time"].iloc[0]),
                test_end=pd.Timestamp(test["entry_time"].iloc[-1]),
                bad_buckets=_learn_bad_buckets(
                    train,
                    min_bucket_trades=min_bucket_trades,
                    max_profit_factor=max_profit_factor,
                    max_mean_return_pct=max_mean_return_pct,
                ),
            )
        )
        start += int(roll_trades)
        fold += 1
    return schedules


def _schedule_for_time(schedules: list[FoldSchedule], ts: pd.Timestamp) -> FoldSchedule | None:
    for schedule in schedules:
        if schedule.test_start <= ts <= schedule.test_end:
            return schedule
    return None


def apply_overlay(
    annotated: pd.DataFrame,
    schedules: list[FoldSchedule],
    *,
    reduce_multiplier: float = 0.0,
) -> pd.DataFrame:
    rows = annotated.sort_values("entry_time").copy()
    multipliers: list[float] = []
    reasons: list[str] = []
    folds: list[int | None] = []
    for _, row in rows.iterrows():
        ts = pd.Timestamp(row["entry_time"])
        schedule = _schedule_for_time(schedules, ts)
        if schedule is None:
            multipliers.append(1.0)
            reasons.append("rotation_overlay:no_test_fold")
            folds.append(None)
            continue
        matched = sorted(set(_bucket_keys(row)).intersection(schedule.bad_buckets))
        folds.append(schedule.fold)
        if matched:
            multipliers.append(float(reduce_multiplier))
            reasons.append("rotation_overlay:reduce:" + ",".join(matched))
        else:
            multipliers.append(1.0)
            reasons.append("rotation_overlay:keep")
    rows["rotation_overlay_fold"] = folds
    rows["rotation_overlay_multiplier"] = multipliers
    rows["rotation_overlay_reason"] = reasons
    rows["overlay_pnl"] = pd.to_numeric(rows["pnl"], errors="coerce").fillna(0.0) * rows["rotation_overlay_multiplier"]
    rows["overlay_pnl_return_pct"] = pd.to_numeric(rows["pnl_return_pct"], errors="coerce").fillna(0.0) * rows["rotation_overlay_multiplier"]
    return rows


def _summary(name: str, frame: pd.DataFrame, pnl_col: str = "pnl", return_col: str = "pnl_return_pct") -> dict[str, Any]:
    if frame.empty:
        return {
            "segment": name,
            "trades": 0,
            "active_trades": 0,
            "win_rate_pct": 0.0,
            "pnl": 0.0,
            "mean_return_pct": 0.0,
            "profit_factor": None,
        }
    pnl = pd.to_numeric(frame[pnl_col], errors="coerce").fillna(0.0)
    returns = pd.to_numeric(frame[return_col], errors="coerce").fillna(0.0)
    pf = _profit_factor(pnl)
    active = int((pd.to_numeric(frame.get("rotation_overlay_multiplier", pd.Series([1.0] * len(frame))), errors="coerce").fillna(1.0) > 0).sum())
    return {
        "segment": name,
        "trades": int(len(frame)),
        "active_trades": active,
        "win_rate_pct": round(float((pnl > 0).sum() / len(frame) * 100.0), 4),
        "pnl": round(float(pnl.sum()), 4),
        "mean_return_pct": round(float(returns.mean()), 4),
        "profit_factor": round(float(pf), 4) if pf is not None and math.isfinite(pf) else None,
    }


def build_report(annotated: pd.DataFrame, schedules: list[FoldSchedule], overlay: pd.DataFrame) -> dict[str, Any]:
    test = overlay[overlay["rotation_overlay_fold"].notna()].copy()
    baseline = _summary("baseline_test", test, "pnl", "pnl_return_pct")
    overlay_summary = _summary("rotation_overlay_test", test, "overlay_pnl", "overlay_pnl_return_pct")
    reduced = test[test["rotation_overlay_multiplier"] < 1.0]
    fold_rows: list[dict[str, Any]] = []
    for schedule in schedules:
        frame = test[test["rotation_overlay_fold"] == schedule.fold]
        base = _summary(f"fold_{schedule.fold}_baseline", frame, "pnl", "pnl_return_pct")
        over = _summary(f"fold_{schedule.fold}_overlay", frame, "overlay_pnl", "overlay_pnl_return_pct")
        fold_rows.append({
            "fold": schedule.fold,
            "test_start": str(schedule.test_start),
            "test_end": str(schedule.test_end),
            "bad_bucket_count": len(schedule.bad_buckets),
            "reduced_trades": int((frame["rotation_overlay_multiplier"] < 1.0).sum()),
            "baseline_pnl": base["pnl"],
            "overlay_pnl": over["pnl"],
            "delta_pnl": round(float(over["pnl"]) - float(base["pnl"]), 4),
        })
    delta = round(float(overlay_summary["pnl"]) - float(baseline["pnl"]), 4)
    return {
        "status": "diagnostic_only",
        "decision": "benchmark_only",
        "baseline": baseline,
        "overlay": overlay_summary,
        "delta_pnl": delta,
        "reduced_trades": int(len(reduced)),
        "folds": fold_rows,
        "learned_bucket_counts": [
            {"fold": schedule.fold, "bad_buckets": list(schedule.bad_buckets)}
            for schedule in schedules
        ],
    }


def write_markdown(report: dict[str, Any], path: str | Path) -> None:
    summary_cols = ["segment", "trades", "active_trades", "win_rate_pct", "pnl", "mean_return_pct", "profit_factor"]
    fold_cols = ["fold", "test_start", "test_end", "bad_bucket_count", "reduced_trades", "baseline_pnl", "overlay_pnl", "delta_pnl"]
    lines = [
        "# Market Rotation Overlay Walk-Forward - 2026-05-05",
        "",
        "Status: diagnostic-only. This does not change paper, testnet, or live behavior.",
        "",
        "Method: train on earlier trades, learn rotation buckets with weak/negative",
        "train behavior, then reduce those buckets only in the next chronological",
        "test slice. This is trade-level research, not a live execution permission.",
        "",
        "## Summary",
        "",
        markdown_table([report["baseline"], report["overlay"]], summary_cols),
        "",
        f"Delta PnL: `{report['delta_pnl']}`",
        f"Reduced trades: `{report['reduced_trades']}`",
        "",
        "## Folds",
        "",
        markdown_table(report["folds"], fold_cols),
        "",
        "## Learned Buckets",
        "",
    ]
    for row in report["learned_bucket_counts"]:
        buckets = ", ".join(row["bad_buckets"]) if row["bad_buckets"] else "(none)"
        lines.append(f"- Fold {row['fold']}: {buckets}")
    lines.extend([
        "",
        "## Decision",
        "",
        "This remains `benchmark_only`. A production gate would need a real",
        "entry-time portfolio backtest, severe cost stress, enough folds, and no",
        "regression in crisis/tail behavior before any activation.",
    ])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Market rotation overlay walk-forward diagnostic")
    parser.add_argument("--trades", default="portfolio_trades.csv")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--lookback-bars", type=int, default=18)
    parser.add_argument("--train-trades", type=int, default=120)
    parser.add_argument("--test-trades", type=int, default=40)
    parser.add_argument("--roll-trades", type=int, default=40)
    parser.add_argument("--min-bucket-trades", type=int, default=5)
    parser.add_argument("--reduce-multiplier", type=float, default=0.0)
    parser.add_argument("--json-out", default="market_rotation_overlay_report.json")
    parser.add_argument("--trades-out", default="market_rotation_overlay_trades.csv")
    parser.add_argument("--md-out", default="docs/MARKET_ROTATION_OVERLAY_WF_2026_05_05.md")
    args = parser.parse_args()

    exchange = make_exchange()
    days = max(1, int(float(args.years) * 365))
    btc = fetch_ohlcv_history(exchange, "BTC/USDT:USDT", timeframe=args.timeframe, days=days)
    eth = fetch_ohlcv_history(exchange, "ETH/USDT:USDT", timeframe=args.timeframe, days=days)
    rotation = rotation_report.build_rotation_frame(btc, eth, timeframe=args.timeframe, lookback_bars=args.lookback_bars)
    trades = pd.read_csv(args.trades)
    annotated = rotation_report.annotate_trades(trades, rotation)
    schedules = build_fold_schedules(
        annotated,
        train_trades=args.train_trades,
        test_trades=args.test_trades,
        roll_trades=args.roll_trades,
        min_bucket_trades=args.min_bucket_trades,
    )
    overlay = apply_overlay(annotated, schedules, reduce_multiplier=args.reduce_multiplier)
    report = build_report(annotated, schedules, overlay)
    Path(args.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    overlay.to_csv(args.trades_out, index=False)
    write_markdown(report, args.md_out)
    print(json.dumps({"decision": report["decision"], "delta_pnl": report["delta_pnl"], "reduced_trades": report["reduced_trades"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
