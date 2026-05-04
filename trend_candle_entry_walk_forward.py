from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import candle_correlation_overlay as cco
import candle_structure
import candle_structure_report
import config
import portfolio_backtest as pb
import strategy as strat
import trend_quality_report


def add_candle_features_to_data(data_by_symbol: dict[str, dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for symbol, payload in data_by_symbol.items():
        updated = dict(payload)
        updated["df"] = candle_structure.add_candle_structure_features(payload["df"])
        out[symbol] = updated
    return out


def dynamic_corr_series_by_symbol(
    data_by_symbol: dict[str, dict],
    *,
    lookback: int = 120,
    min_periods: int = 40,
) -> dict[str, pd.Series]:
    closes = {
        symbol: pd.to_numeric(payload["df"]["close"], errors="coerce")
        for symbol, payload in data_by_symbol.items()
    }
    returns = pd.DataFrame(closes).sort_index().pct_change()
    out: dict[str, pd.Series] = {}
    for symbol in returns.columns:
        others = [col for col in returns.columns if col != symbol]
        if not others:
            out[symbol] = pd.Series(0.0, index=returns.index)
            continue
        corrs = [
            returns[symbol].rolling(int(lookback), min_periods=int(min_periods)).corr(returns[other]).abs()
            for other in others
        ]
        out[symbol] = pd.concat(corrs, axis=1).max(axis=1).fillna(0.0).round(6)
    return out


def _lookup_corr(corr_series: dict[str, pd.Series], symbol: str, ts) -> float:
    series = corr_series.get(symbol)
    if series is None or series.empty:
        return 0.0
    eligible = series.loc[series.index <= pd.to_datetime(ts)]
    if eligible.empty:
        return 0.0
    return float(eligible.iloc[-1] or 0.0)


def entry_setup_bucket(
    *,
    symbol: str,
    ts,
    bar: pd.Series,
    signal: str,
    risk_reasons: tuple[str, ...] | list[str],
    corr_series: dict[str, pd.Series],
) -> str:
    side_bias = 1 if signal == strat.LONG else -1
    candle_bias = int(float(bar.get("candle_structure_bias", 0.0) or 0.0))
    if candle_bias == side_bias:
        alignment = "aligned"
    elif candle_bias == 0:
        alignment = "neutral"
    else:
        alignment = "contra"
    return cco.setup_bucket(
        pd.Series(
            {
                "candle_structure_alignment": alignment,
                "symbol_dynamic_max_abs_corr": _lookup_corr(corr_series, symbol, ts),
                "risk_reasons": "|".join(risk_reasons),
            }
        )
    )


def annotate_baseline_trades(
    trades: pd.DataFrame,
    data_by_symbol: dict[str, dict],
    corr_series: dict[str, pd.Series],
    symbols: list[str],
) -> pd.DataFrame:
    static_corr = candle_structure_report.max_abs_corr_by_symbol(data_by_symbol, symbols)
    annotated = candle_structure_report.annotate_trades(trades, data_by_symbol, symbol_max_abs_corr=static_corr)
    annotated["symbol_dynamic_max_abs_corr"] = [
        _lookup_corr(corr_series, str(row["symbol"]), row.get("signal_bar_time", row["entry_time"]))
        for _, row in annotated.iterrows()
    ]
    annotated["setup_bucket"] = annotated.apply(cco.setup_bucket, axis=1)
    return annotated.sort_values("entry_time").reset_index(drop=True)


def build_fold_schedules(
    annotated: pd.DataFrame,
    *,
    train_trades: int = 160,
    test_trades: int = 40,
    roll_trades: int = 40,
    min_bucket_trades: int = 12,
    reduce_multiplier: float = 0.5,
) -> list[dict[str, Any]]:
    schedules: list[dict[str, Any]] = []
    start = 0
    fold = 0
    while start + int(train_trades) < len(annotated):
        train_start = start
        train_end = start + int(train_trades)
        test_end = min(train_end + int(test_trades), len(annotated))
        train = annotated.iloc[train_start:train_end]
        test = annotated.iloc[train_end:test_end]
        if test.empty:
            break
        rules = cco.learn_bad_setup_rules(
            train,
            min_bucket_trades=min_bucket_trades,
            reduce_multiplier=reduce_multiplier,
        )
        schedules.append(
            {
                "fold": fold,
                "train_start": int(train_start),
                "train_end": int(train_end),
                "test_start": int(train_end),
                "test_end": int(test_end),
                "test_start_time": pd.to_datetime(test["entry_time"].min()),
                "test_end_time": pd.to_datetime(test["entry_time"].max()),
                "rules": rules,
                "learned_rule_count": len(rules),
                "baseline_test_trades": int(len(test)),
            }
        )
        if test_end >= len(annotated):
            break
        start += int(roll_trades)
        fold += 1
    return schedules


def make_entry_overlay(schedules: list[dict[str, Any]], corr_series: dict[str, pd.Series]):
    def overlay(**kwargs):
        entry_time = pd.to_datetime(kwargs["entry_time"])
        schedule = None
        for item in schedules:
            if item["test_start_time"] <= entry_time <= item["test_end_time"]:
                schedule = item
                break
        if schedule is None:
            return None
        risk_decision = kwargs["risk_decision"]
        bucket = entry_setup_bucket(
            symbol=kwargs["symbol"],
            ts=kwargs["ts"],
            bar=kwargs["bar"],
            signal=kwargs["signal"],
            risk_reasons=tuple(risk_decision.reasons),
            corr_series=corr_series,
        )
        rule = schedule["rules"].get(bucket)
        if not rule:
            return {
                "multiplier": 1.0,
                "reasons": (f"tcwf:no_bad_train_evidence:{schedule['fold']}",),
            }
        return {
            "multiplier": float(rule["multiplier"]),
            "reasons": (f"tcwf:reduce:{schedule['fold']}:{bucket}",),
        }

    return overlay


def _in_oos(entry_times: pd.Series, schedules: list[dict[str, Any]]) -> pd.Series:
    times = pd.to_datetime(entry_times)
    mask = pd.Series(False, index=times.index)
    for schedule in schedules:
        mask = mask | ((times >= schedule["test_start_time"]) & (times <= schedule["test_end_time"]))
    return mask


def _profit_factor(pnl: pd.Series) -> float | None:
    pnl = pd.to_numeric(pnl, errors="coerce").fillna(0.0)
    wins = float(pnl[pnl > 0].sum())
    losses = abs(float(pnl[pnl < 0].sum()))
    if losses == 0:
        return None
    return wins / losses


def summarize_trades(name: str, trades: pd.DataFrame, *, start_balance: float = 1000.0) -> dict[str, Any]:
    if trades.empty:
        return {
            "segment": name,
            "trades": 0,
            "total_pnl": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "ending_equity": float(start_balance),
            "max_dd": 0.0,
            "max_dd_pct": 0.0,
        }
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0.0)
    equity = float(start_balance) + pnl.cumsum()
    peak = equity.cummax()
    dd = peak - equity
    pf = _profit_factor(pnl)
    return {
        "segment": name,
        "trades": int(len(trades)),
        "total_pnl": round(float(pnl.sum()), 4),
        "avg_pnl": round(float(pnl.mean()), 4),
        "win_rate_pct": round(float((pnl > 0).mean() * 100.0), 4),
        "profit_factor": round(float(pf), 4) if pf is not None else None,
        "ending_equity": round(float(equity.iloc[-1]), 4),
        "max_dd": round(float(dd.max()), 4),
        "max_dd_pct": round(float((dd / peak.replace(0, pd.NA)).max() * 100.0), 4),
    }


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _format(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format(row.get(col)) for col in columns) + " |")
    return "\n".join(lines)


def write_markdown(report: dict[str, Any], path: str | Path, *, years: int) -> None:
    summary_cols = [
        "segment",
        "trades",
        "total_pnl",
        "win_rate_pct",
        "profit_factor",
        "ending_equity",
        "max_dd",
        "max_dd_pct",
    ]
    fold_rows = [
        {
            "fold": row["fold"],
            "baseline_test_trades": row["baseline_test_trades"],
            "learned_rule_count": row["learned_rule_count"],
        }
        for row in report["fold_schedules"]
    ]
    lines = [
        "# Trend/Candle Entry Walk-Forward - 2026-05-04",
        "",
        "This is a true entry-time side-by-side research backtest. It does not",
        "change paper, testnet, or live behavior.",
        "",
        f"Historical data window: `{years}` years",
        "",
        "## Rule",
        "",
        "- Baseline Donchian logic stays unchanged.",
        "- Train folds learn bad setup buckets from closed-bar trend quality,",
        "  candle-structure alignment, and dynamic symbol correlation.",
        "- Test folds reduce only train-proven bad buckets.",
        "- No candle/correlation feature can increase position size.",
        "",
        "## OOS Result",
        "",
        markdown_table([report["baseline_oos"], report["overlay_oos"]], summary_cols),
        "",
        f"- OOS PnL delta: `{report['delta_total_pnl']}`",
        f"- OOS max DD delta: `{report['delta_max_dd']}`",
        f"- Reduced overlay trades: `{report['reduced_overlay_trades']}`",
        "",
        "## Fold Summary",
        "",
        markdown_table(fold_rows, ["fold", "baseline_test_trades", "learned_rule_count"]),
        "",
        "## Decision",
        "",
        "If this report does not improve OOS PnL or drawdown, the feature remains",
        "research-only and must not be promoted to paper/testnet.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_report(
    *,
    symbols: list[str] | None = None,
    years: int = 3,
    train_trades: int = 160,
    test_trades: int = 40,
    roll_trades: int = 40,
    min_bucket_trades: int = 12,
    reduce_multiplier: float = 0.5,
    baseline_out: str = "trend_candle_wf_baseline_trades.csv",
    overlay_out: str = "trend_candle_wf_overlay_trades.csv",
    json_out: str = "trend_candle_entry_walk_forward.json",
    md_out: str = "docs/TREND_CANDLE_ENTRY_WALK_FORWARD_2026_05_04.md",
) -> dict[str, Any]:
    symbols = symbols or list(config.SYMBOLS)
    data = add_candle_features_to_data(pb.fetch_all_data(symbols, years=years))
    corr_series = dynamic_corr_series_by_symbol(data)

    baseline_trades, baseline_equity = pb.run_portfolio_backtest(
        symbols,
        data,
        start_balance=config.CAPITAL_USDT,
        max_concurrent=config.MAX_OPEN_POSITIONS,
    )
    annotated = annotate_baseline_trades(baseline_trades, data, corr_series, symbols)
    schedules = build_fold_schedules(
        annotated,
        train_trades=train_trades,
        test_trades=test_trades,
        roll_trades=roll_trades,
        min_bucket_trades=min_bucket_trades,
        reduce_multiplier=reduce_multiplier,
    )
    overlay_trades, overlay_equity = pb.run_portfolio_backtest(
        symbols,
        data,
        start_balance=config.CAPITAL_USDT,
        max_concurrent=config.MAX_OPEN_POSITIONS,
        entry_risk_overlay=make_entry_overlay(schedules, corr_series),
    )

    baseline_oos = baseline_trades[_in_oos(baseline_trades["entry_time"], schedules)].copy()
    overlay_oos = overlay_trades[_in_oos(overlay_trades["entry_time"], schedules)].copy()
    reduced_overlay = overlay_oos[
        pd.to_numeric(overlay_oos.get("entry_overlay_mult", pd.Series(dtype=float)), errors="coerce").fillna(1.0) < 1.0
    ]
    report = {
        "baseline_oos": summarize_trades("baseline_oos", baseline_oos, start_balance=config.CAPITAL_USDT),
        "overlay_oos": summarize_trades("entry_time_overlay_oos", overlay_oos, start_balance=config.CAPITAL_USDT),
        "delta_total_pnl": round(float(pd.to_numeric(overlay_oos["pnl"], errors="coerce").sum() - pd.to_numeric(baseline_oos["pnl"], errors="coerce").sum()), 4),
        "delta_max_dd": round(
            float(
                summarize_trades("overlay", overlay_oos, start_balance=config.CAPITAL_USDT)["max_dd"]
                - summarize_trades("baseline", baseline_oos, start_balance=config.CAPITAL_USDT)["max_dd"]
            ),
            4,
        ),
        "reduced_overlay_trades": int(len(reduced_overlay)),
        "fold_schedules": schedules,
        "baseline_equity_end": float(baseline_equity["equity"].iloc[-1]) if not baseline_equity.empty else None,
        "overlay_equity_end": float(overlay_equity["equity"].iloc[-1]) if not overlay_equity.empty else None,
    }
    if baseline_out:
        baseline_trades.to_csv(baseline_out, index=False)
    if overlay_out:
        overlay_trades.to_csv(overlay_out, index=False)
    if json_out:
        Path(json_out).write_text(json.dumps(_clean(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if md_out:
        write_markdown(report, md_out, years=years)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="True entry-time trend/candle walk-forward reducer.")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--train-trades", type=int, default=160)
    parser.add_argument("--test-trades", type=int, default=40)
    parser.add_argument("--roll-trades", type=int, default=40)
    parser.add_argument("--min-bucket-trades", type=int, default=12)
    parser.add_argument("--reduce-multiplier", type=float, default=0.5)
    parser.add_argument("--baseline-out", default="trend_candle_wf_baseline_trades.csv")
    parser.add_argument("--overlay-out", default="trend_candle_wf_overlay_trades.csv")
    parser.add_argument("--json-out", default="trend_candle_entry_walk_forward.json")
    parser.add_argument("--md-out", default="docs/TREND_CANDLE_ENTRY_WALK_FORWARD_2026_05_04.md")
    args = parser.parse_args()
    report = run_report(
        symbols=args.symbols,
        years=args.years,
        train_trades=args.train_trades,
        test_trades=args.test_trades,
        roll_trades=args.roll_trades,
        min_bucket_trades=args.min_bucket_trades,
        reduce_multiplier=args.reduce_multiplier,
        baseline_out=args.baseline_out,
        overlay_out=args.overlay_out,
        json_out=args.json_out,
        md_out=args.md_out,
    )
    print(json.dumps(_clean(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
