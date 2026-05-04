from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

import candle_structure_report
import config
import portfolio_backtest as pb
import trend_quality_report


def corr_bucket(value: float, *, high: float = 0.65, extreme: float = 0.75) -> str:
    value = abs(float(value or 0.0))
    if value >= float(extreme):
        return "corr_extreme"
    if value >= float(high):
        return "corr_high"
    return "corr_normal"


def setup_bucket(row: pd.Series) -> str:
    tokens = trend_quality_report.reason_tokens(row.get("risk_reasons", ""))
    trend_bucket = trend_quality_report.trend_quality_bucket(trend_quality_report.trend_quality_score(tokens))
    return "|".join(
        [
            str(row.get("candle_structure_alignment", "neutral")),
            corr_bucket(float(row.get("symbol_dynamic_max_abs_corr", row.get("symbol_max_abs_corr", 0.0)) or 0.0)),
            f"trend_{trend_bucket}",
        ]
    )


def dynamic_max_abs_corr_by_trade(
    annotated: pd.DataFrame,
    data_by_symbol: dict[str, dict],
    *,
    lookback: int = 120,
    min_periods: int = 40,
) -> pd.Series:
    closes = {
        symbol: pd.to_numeric(data["df"]["close"], errors="coerce")
        for symbol, data in data_by_symbol.items()
        if "df" in data and "close" in data["df"].columns
    }
    if not closes:
        return pd.Series([0.0] * len(annotated), index=annotated.index)
    returns = pd.DataFrame(closes).sort_index().pct_change()
    out: list[float] = []
    for _, row in annotated.iterrows():
        symbol = str(row.get("symbol", ""))
        if symbol not in returns.columns:
            out.append(0.0)
            continue
        signal_time = pd.to_datetime(row.get("signal_bar_time", row.get("entry_time")))
        window = returns.loc[returns.index <= signal_time].tail(int(lookback)).dropna(how="all")
        if len(window) < int(min_periods):
            out.append(0.0)
            continue
        corr = window.corr()[symbol].drop(labels=[symbol], errors="ignore").abs().dropna()
        out.append(round(float(corr.max()) if not corr.empty else 0.0, 6))
    return pd.Series(out, index=annotated.index)


def _profit_factor(pnl: pd.Series) -> float | None:
    pnl = pd.to_numeric(pnl, errors="coerce").fillna(0.0)
    wins = float(pnl[pnl > 0].sum())
    losses = abs(float(pnl[pnl < 0].sum()))
    if losses == 0:
        return None
    return wins / losses


def learn_bad_setup_rules(
    train: pd.DataFrame,
    *,
    min_bucket_trades: int = 12,
    reduce_multiplier: float = 0.5,
) -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    if train.empty:
        return rules
    frame = train.copy()
    if "setup_bucket" not in frame.columns:
        frame["setup_bucket"] = frame.apply(setup_bucket, axis=1)
    for bucket, part in frame.groupby("setup_bucket"):
        if len(part) < int(min_bucket_trades):
            continue
        pnl = pd.to_numeric(part["pnl"], errors="coerce").fillna(0.0)
        pf = _profit_factor(pnl)
        total = float(pnl.sum())
        win_rate = float((pnl > 0).mean() * 100.0)
        # Conservative gate: only reduce setups that were outright unprofitable
        # in the train slice and had profit factor below breakeven.
        if total < 0.0 and pf is not None and pf < 1.0:
            rules[str(bucket)] = {
                "bucket": str(bucket),
                "train_trades": int(len(part)),
                "train_total_pnl": round(total, 4),
                "train_avg_pnl": round(float(pnl.mean()), 4),
                "train_win_rate_pct": round(win_rate, 4),
                "train_profit_factor": round(float(pf), 4),
                "multiplier": round(float(reduce_multiplier), 4),
            }
    return rules


def apply_walk_forward_reducer(
    annotated: pd.DataFrame,
    *,
    train_trades: int = 160,
    test_trades: int = 40,
    roll_trades: int = 40,
    min_bucket_trades: int = 12,
    reduce_multiplier: float = 0.5,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out = annotated.sort_values("entry_time").reset_index(drop=True).copy()
    out["setup_bucket"] = out.apply(setup_bucket, axis=1)
    out["wf_is_test"] = False
    out["wf_fold"] = pd.NA
    out["overlay_multiplier"] = 1.0
    out["overlay_reason"] = "not_oos"
    out["overlay_pnl"] = pd.to_numeric(out["pnl"], errors="coerce").fillna(0.0)
    out["overlay_pnl_delta"] = 0.0

    fold_reports: list[dict[str, Any]] = []
    fold = 0
    start = 0
    while start + int(train_trades) < len(out):
        train_start = start
        train_end = start + int(train_trades)
        test_end = min(train_end + int(test_trades), len(out))
        train = out.iloc[train_start:train_end]
        rules = learn_bad_setup_rules(
            train,
            min_bucket_trades=min_bucket_trades,
            reduce_multiplier=reduce_multiplier,
        )
        test_index = out.index[train_end:test_end]
        for idx in test_index:
            bucket = str(out.at[idx, "setup_bucket"])
            out.at[idx, "wf_is_test"] = True
            out.at[idx, "wf_fold"] = fold
            rule = rules.get(bucket)
            if rule:
                multiplier = float(rule["multiplier"])
                out.at[idx, "overlay_multiplier"] = multiplier
                out.at[idx, "overlay_reason"] = f"train_bad_setup:{bucket}"
            else:
                out.at[idx, "overlay_reason"] = "no_bad_train_evidence"
            pnl = float(out.at[idx, "pnl"])
            out.at[idx, "overlay_pnl"] = round(pnl * float(out.at[idx, "overlay_multiplier"]), 6)
            out.at[idx, "overlay_pnl_delta"] = round(float(out.at[idx, "overlay_pnl"]) - pnl, 6)

        fold_reports.append(
            {
                "fold": fold,
                "train_start": int(train_start),
                "train_end": int(train_end),
                "test_start": int(train_end),
                "test_end": int(test_end),
                "learned_bad_rules": list(rules.values()),
                "test_trades": int(len(test_index)),
                "reduced_test_trades": int((out.loc[test_index, "overlay_multiplier"] < 1.0).sum()),
            }
        )
        if test_end >= len(out):
            break
        start += int(roll_trades)
        fold += 1
    return out, fold_reports


def summarize_pnl(name: str, pnl: pd.Series, *, start_balance: float = 1000.0) -> dict[str, Any]:
    pnl = pd.to_numeric(pnl, errors="coerce").fillna(0.0)
    equity = float(start_balance) + pnl.cumsum()
    peak = equity.cummax()
    dd = peak - equity
    pf = _profit_factor(pnl)
    return {
        "segment": name,
        "trades": int(len(pnl)),
        "total_pnl": round(float(pnl.sum()), 4),
        "avg_pnl": round(float(pnl.mean()) if len(pnl) else 0.0, 4),
        "win_rate_pct": round(float((pnl > 0).mean() * 100.0) if len(pnl) else 0.0, 4),
        "profit_factor": round(float(pf), 4) if pf is not None else None,
        "ending_equity": round(float(equity.iloc[-1]) if len(equity) else float(start_balance), 4),
        "max_dd": round(float(dd.max()) if len(dd) else 0.0, 4),
        "max_dd_pct": round(float((dd / peak.replace(0, pd.NA)).max() * 100.0) if len(dd) else 0.0, 4),
    }


def build_report(overlaid: pd.DataFrame, folds: list[dict[str, Any]], *, start_balance: float = 1000.0) -> dict[str, Any]:
    oos = overlaid[overlaid["wf_is_test"] == True].copy()
    baseline = summarize_pnl("oos_baseline", oos["pnl"], start_balance=start_balance)
    overlay = summarize_pnl("oos_train_gated_reducer", oos["overlay_pnl"], start_balance=start_balance)
    reduced = oos[oos["overlay_multiplier"] < 1.0]
    by_bucket = []
    for bucket, part in reduced.groupby("setup_bucket", dropna=False):
        row = summarize_pnl(str(bucket), part["overlay_pnl_delta"], start_balance=0.0)
        row["avg_multiplier"] = round(float(pd.to_numeric(part["overlay_multiplier"], errors="coerce").mean()), 4)
        by_bucket.append(row)
    return {
        "baseline": baseline,
        "overlay": overlay,
        "delta_total_pnl": round(float(overlay["total_pnl"] - baseline["total_pnl"]), 4),
        "delta_max_dd": round(float(overlay["max_dd"] - baseline["max_dd"]), 4),
        "folds": folds,
        "oos_trades": int(len(oos)),
        "reduced_oos_trades": int(len(reduced)),
        "by_reduced_bucket_delta": sorted(by_bucket, key=lambda row: str(row["segment"])),
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


def write_markdown(report: dict[str, Any], path: str | Path, *, source: str, years: int) -> None:
    summary_columns = [
        "segment",
        "trades",
        "total_pnl",
        "win_rate_pct",
        "profit_factor",
        "ending_equity",
        "max_dd",
        "max_dd_pct",
    ]
    delta_columns = ["segment", "trades", "total_pnl", "avg_pnl", "max_dd", "avg_multiplier"]
    fold_rows = [
        {
            "fold": row["fold"],
            "test_trades": row["test_trades"],
            "reduced_test_trades": row["reduced_test_trades"],
            "learned_rule_count": len(row["learned_bad_rules"]),
        }
        for row in report["folds"]
    ]
    lines = [
        "# Candle Correlation Train-Gated Reducer - 2026-05-04",
        "",
        "This is a backtest-only algorithm prototype. It does not change active",
        "strategy, paper runner, testnet, or live behavior.",
        "",
        f"Source trades file: `{source}`",
        f"Historical data window: `{years}` years",
        "",
        "## Rule",
        "",
        "- Never increase position size from candle or correlation features.",
        "- Learn bad setup buckets only from the train slice.",
        "- Reduce only buckets that were negative in train and had profit factor below `1.0`.",
        "- Setup bucket = candle alignment + dynamic return-correlation bucket + trend-quality bucket.",
        "- Correlation is calculated from closed-bar returns available before the trade.",
        "",
        "## OOS Result",
        "",
        markdown_table([report["baseline"], report["overlay"]], summary_columns),
        "",
        f"- OOS trades: `{report['oos_trades']}`",
        f"- Reduced OOS trades: `{report['reduced_oos_trades']}`",
        f"- Total PnL delta: `{report['delta_total_pnl']}`",
        f"- Max drawdown delta: `{report['delta_max_dd']}`",
        "",
        "## Fold Summary",
        "",
        markdown_table(fold_rows, ["fold", "test_trades", "reduced_test_trades", "learned_rule_count"]),
        "",
        "## Reduced Bucket Contribution",
        "",
        markdown_table(report["by_reduced_bucket_delta"], delta_columns),
        "",
        "## Decision",
        "",
        "If OOS PnL or drawdown does not improve, this reducer stays report-only.",
        "It should not be promoted into paper/testnet until a true entry-time",
        "position-sizing backtest and walk-forward both show net improvement.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_report(
    *,
    trades_path: str = "portfolio_trades.csv",
    symbols: list[str] | None = None,
    years: int = 3,
    train_trades: int = 160,
    test_trades: int = 40,
    roll_trades: int = 40,
    min_bucket_trades: int = 12,
    reduce_multiplier: float = 0.5,
    overlay_out: str = "candle_correlation_overlay_trades.csv",
    json_out: str = "candle_correlation_overlay.json",
    md_out: str = "docs/CANDLE_CORRELATION_OVERLAY_2026_05_04.md",
) -> dict[str, Any]:
    symbols = symbols or list(config.SYMBOLS)
    trades = pd.read_csv(trades_path)
    data = pb.fetch_all_data(symbols, years=years)
    static_corr = candle_structure_report.max_abs_corr_by_symbol(data, symbols)
    annotated = candle_structure_report.annotate_trades(trades, data, symbol_max_abs_corr=static_corr)
    annotated["symbol_dynamic_max_abs_corr"] = dynamic_max_abs_corr_by_trade(annotated, data)
    overlaid, folds = apply_walk_forward_reducer(
        annotated,
        train_trades=train_trades,
        test_trades=test_trades,
        roll_trades=roll_trades,
        min_bucket_trades=min_bucket_trades,
        reduce_multiplier=reduce_multiplier,
    )
    report = {
        "symbol_static_max_abs_corr": static_corr,
        **build_report(overlaid, folds, start_balance=float(config.CAPITAL_USDT)),
    }
    if overlay_out:
        overlaid.to_csv(overlay_out, index=False)
    if json_out:
        Path(json_out).write_text(json.dumps(_clean(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if md_out:
        write_markdown(report, md_out, source=trades_path, years=years)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest-only train-gated candle/correlation risk reducer.")
    parser.add_argument("--trades", default="portfolio_trades.csv")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--train-trades", type=int, default=160)
    parser.add_argument("--test-trades", type=int, default=40)
    parser.add_argument("--roll-trades", type=int, default=40)
    parser.add_argument("--min-bucket-trades", type=int, default=12)
    parser.add_argument("--reduce-multiplier", type=float, default=0.5)
    parser.add_argument("--overlay-out", default="candle_correlation_overlay_trades.csv")
    parser.add_argument("--json-out", default="candle_correlation_overlay.json")
    parser.add_argument("--md-out", default="docs/CANDLE_CORRELATION_OVERLAY_2026_05_04.md")
    args = parser.parse_args()
    report = run_report(
        trades_path=args.trades,
        symbols=args.symbols,
        years=args.years,
        train_trades=args.train_trades,
        test_trades=args.test_trades,
        roll_trades=args.roll_trades,
        min_bucket_trades=args.min_bucket_trades,
        reduce_multiplier=args.reduce_multiplier,
        overlay_out=args.overlay_out,
        json_out=args.json_out,
        md_out=args.md_out,
    )
    print(json.dumps(_clean(report), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
