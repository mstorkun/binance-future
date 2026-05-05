from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import carry_research
from hurst_mtf_momentum_report import fetch_ohlcv_history, make_exchange, markdown_table, resample_ohlcv
import risk_metrics
import volatility_breakout_signal as signal


DEFAULT_CLAUDE_FOLDS = (2, 5, 10, 12)


def _annualized_vol(close: pd.Series, window: int) -> pd.Series:
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], pd.NA)
    return returns.rolling(int(window), min_periods=max(12, int(window) // 3)).std(ddof=1) * math.sqrt(24.0 * 365.0)


def _btc_regime_frame(btc_1h: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(btc_1h["close"], errors="coerce")
    h1 = signal.h1_breakout_features(btc_1h)
    btc = signal.btc_context_features(btc_1h)
    h4 = signal.h4_context_features(resample_ohlcv(btc_1h, "4h"))
    h4 = h4.copy()
    h4.index = h4.index + pd.Timedelta(hours=4)
    h4 = h4.reindex(btc_1h.index, method="ffill")
    out = pd.DataFrame(
        {
            "btc_close": close,
            "btc_ret_pct": close.pct_change() * 100.0,
            "btc_ret_4h_pct": close.pct_change(4) * 100.0,
            "btc_ret_24h_pct": close.pct_change(24) * 100.0,
            "btc_vol_24h": _annualized_vol(close, 24),
            "btc_vol_72h": _annualized_vol(close, 72),
            "btc_vol_168h": _annualized_vol(close, 168),
            "btc_side": btc["btc_side"],
            "btc_shock_z": btc["btc_shock_z"],
            "btc_h4_side": h4["h4_side"],
            "btc_h4_adx": h4["h4_adx"],
            "btc_sq120": h1["sq120_recent_squeeze"],
            "btc_sq240": h1["sq240_recent_squeeze"],
            "btc_volume_z": h1["h1_volume_z"],
        },
        index=btc_1h.index,
    )
    return out.replace([float("inf"), float("-inf")], pd.NA)


def _funding_frame(exchange: Any, symbol: str, *, days: int) -> pd.DataFrame:
    try:
        rates = carry_research.fetch_funding_history(exchange, symbol, days=days)
    except Exception:
        return pd.DataFrame(columns=["funding_rate"])
    if rates.empty:
        return pd.DataFrame(columns=["funding_rate"])
    rates = rates.copy()
    rates.index = pd.to_datetime(rates.index, utc=True)
    return rates.sort_index()


def _scenario_map(results: pd.DataFrame, scenario: str) -> dict[int, float]:
    rows = results[results["scenario"] == scenario].copy()
    rows["period"] = pd.to_numeric(rows["period"], errors="coerce").astype("Int64")
    rows["total_return_pct"] = pd.to_numeric(rows["total_return_pct"], errors="coerce")
    return {int(row["period"]): float(row["total_return_pct"]) for _, row in rows.dropna(subset=["period"]).iterrows()}


def _summarize_window(regime: pd.DataFrame, funding: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    window = regime.loc[(regime.index >= start) & (regime.index <= end)]
    funding_window = funding.loc[(funding.index >= start) & (funding.index <= end)] if not funding.empty else pd.DataFrame()
    if window.empty:
        return {}
    ret_total = float(window["btc_close"].iloc[-1] / window["btc_close"].iloc[0] - 1.0) * 100.0
    shock = pd.to_numeric(window["btc_shock_z"], errors="coerce").abs()
    funding_values = pd.to_numeric(funding_window.get("funding_rate", pd.Series(dtype=float)), errors="coerce").dropna()
    return {
        "btc_return_pct": ret_total,
        "btc_vol_24h_mean": float(pd.to_numeric(window["btc_vol_24h"], errors="coerce").mean()),
        "btc_vol_72h_mean": float(pd.to_numeric(window["btc_vol_72h"], errors="coerce").mean()),
        "btc_vol_168h_mean": float(pd.to_numeric(window["btc_vol_168h"], errors="coerce").mean()),
        "btc_side_long_share": float((pd.to_numeric(window["btc_side"], errors="coerce") > 0).mean()),
        "btc_side_short_share": float((pd.to_numeric(window["btc_side"], errors="coerce") < 0).mean()),
        "btc_h4_long_share": float((pd.to_numeric(window["btc_h4_side"], errors="coerce") > 0).mean()),
        "btc_h4_short_share": float((pd.to_numeric(window["btc_h4_side"], errors="coerce") < 0).mean()),
        "btc_h4_adx_mean": float(pd.to_numeric(window["btc_h4_adx"], errors="coerce").mean()),
        "btc_sq120_mean": float(pd.to_numeric(window["btc_sq120"], errors="coerce").mean()),
        "btc_sq240_mean": float(pd.to_numeric(window["btc_sq240"], errors="coerce").mean()),
        "btc_volume_z_mean": float(pd.to_numeric(window["btc_volume_z"], errors="coerce").mean()),
        "btc_abs_shock_gt2_share": float((shock > 2.0).mean()),
        "btc_abs_shock_gt3_share": float((shock > 3.0).mean()),
        "funding_records": int(len(funding_values)),
        "btc_funding_mean": float(funding_values.mean()) if len(funding_values) else 0.0,
        "btc_funding_abs_mean": float(funding_values.abs().mean()) if len(funding_values) else 0.0,
        "btc_funding_positive_share": float((funding_values > 0.0).mean()) if len(funding_values) else 0.0,
    }


def _group_mean(rows: pd.DataFrame, mask: pd.Series, columns: list[str]) -> dict[str, Any]:
    group = rows.loc[mask, columns]
    if group.empty:
        return {"folds": 0}
    values = {"folds": int(len(group))}
    for column in columns:
        values[column] = float(pd.to_numeric(group[column], errors="coerce").mean())
    return values


def _diff_table(rows: pd.DataFrame, group_col: str, columns: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    mask = rows[group_col].astype(bool)
    selected = rows.loc[mask]
    other = rows.loc[~mask]
    for column in columns:
        left = float(pd.to_numeric(selected[column], errors="coerce").mean()) if not selected.empty else 0.0
        right = float(pd.to_numeric(other[column], errors="coerce").mean()) if not other.empty else 0.0
        out.append({"metric": column, "selected_mean": round(left, 6), "other_mean": round(right, 6), "delta": round(left - right, 6)})
    return out


def build_report(
    *,
    selected_path: str | Path,
    results_path: str | Path,
    years: float = 3.0,
    claude_folds: tuple[int, ...] = DEFAULT_CLAUDE_FOLDS,
) -> dict[str, Any]:
    payload = json.loads(Path(selected_path).read_text(encoding="utf-8"))
    selected = pd.DataFrame(payload.get("selected", []))
    results = pd.read_csv(results_path)
    baseline_returns = _scenario_map(results, "baseline")
    severe_returns = _scenario_map(results, "severe")

    exchange = make_exchange()
    days = max(30, int(float(years) * 365.0))
    btc_1h = fetch_ohlcv_history(exchange, "BTC/USDT:USDT", timeframe="1h", days=days)
    regime = _btc_regime_frame(btc_1h)
    funding = _funding_frame(exchange, "BTC/USDT:USDT", days=days)

    fold_rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        period = int(row["period"])
        start = pd.to_datetime(row["test_start"], utc=True)
        end = pd.to_datetime(row["test_end"], utc=True)
        summary = _summarize_window(regime, funding, start, end)
        baseline = float(baseline_returns.get(period, 0.0))
        severe = float(severe_returns.get(period, 0.0))
        fold_rows.append(
            {
                "period": period,
                "test_start": start.isoformat(),
                "test_end": end.isoformat(),
                "candidate": row.get("candidate", ""),
                "baseline_return_pct": baseline,
                "severe_return_pct": severe,
                "baseline_positive": baseline > 0.0,
                "severe_positive": severe > 0.0,
                "claude_fold": period in set(claude_folds),
                **summary,
            }
        )

    folds = pd.DataFrame(fold_rows)
    diagnostic_columns = [
        "btc_return_pct",
        "btc_vol_24h_mean",
        "btc_vol_72h_mean",
        "btc_vol_168h_mean",
        "btc_side_long_share",
        "btc_side_short_share",
        "btc_h4_long_share",
        "btc_h4_short_share",
        "btc_h4_adx_mean",
        "btc_sq120_mean",
        "btc_sq240_mean",
        "btc_volume_z_mean",
        "btc_abs_shock_gt2_share",
        "btc_abs_shock_gt3_share",
        "btc_funding_mean",
        "btc_funding_abs_mean",
        "btc_funding_positive_share",
    ]
    groups = {
        "baseline_positive": _group_mean(folds, folds["baseline_positive"], diagnostic_columns),
        "severe_positive": _group_mean(folds, folds["severe_positive"], diagnostic_columns),
        "claude_claimed": _group_mean(folds, folds["claude_fold"], diagnostic_columns),
    }
    diffs = {
        "baseline_positive_vs_rest": _diff_table(folds, "baseline_positive", diagnostic_columns),
        "severe_positive_vs_rest": _diff_table(folds, "severe_positive", diagnostic_columns),
        "claude_claimed_vs_rest": _diff_table(folds, "claude_fold", diagnostic_columns),
    }
    return {
        "status": "diagnostic_only",
        "source": {"selected_path": str(selected_path), "results_path": str(results_path), "years": float(years)},
        "claude_claimed_folds": list(claude_folds),
        "current_run_positive_folds": {
            "baseline": [int(row["period"]) for row in fold_rows if row["baseline_positive"]],
            "severe": [int(row["period"]) for row in fold_rows if row["severe_positive"]],
        },
        "folds": risk_metrics.rounded_nested(fold_rows),
        "groups": risk_metrics.rounded_nested(groups),
        "diffs": risk_metrics.rounded_nested(diffs),
        "notes": [
            "This diagnostic is not a trading rule.",
            "A regime gate must be tested as a new walk-forward candidate before paper or live use.",
            "If severe-positive folds are too few, prefer baseline-positive diagnostics only as a hypothesis, not proof.",
        ],
    }


def write_markdown(report: dict[str, Any], path: str | Path) -> None:
    folds = report["folds"]
    groups = report["groups"]
    severe_diffs = report["diffs"]["severe_positive_vs_rest"]
    baseline_diffs = report["diffs"]["baseline_positive_vs_rest"]
    claude_diffs = report["diffs"]["claude_claimed_vs_rest"]
    lines = [
        "# Volatility Breakout Regime Diagnostics - 2026-05-05",
        "",
        "Status: diagnostic-only. This does not enable paper, testnet, or live execution.",
        "",
        "## Fold Sets",
        "",
        f"- Current baseline-positive folds: `{report['current_run_positive_folds']['baseline']}`",
        f"- Current severe-positive folds: `{report['current_run_positive_folds']['severe']}`",
        f"- Claude-claimed folds checked separately: `{report['claude_claimed_folds']}`",
        "",
        "## Fold Regime Rows",
        "",
        markdown_table(
            folds,
            [
                "period",
                "baseline_return_pct",
                "severe_return_pct",
                "baseline_positive",
                "severe_positive",
                "claude_fold",
                "btc_return_pct",
                "btc_vol_72h_mean",
                "btc_h4_adx_mean",
                "btc_h4_long_share",
                "btc_h4_short_share",
                "btc_funding_mean",
            ],
        ),
        "",
        "## Group Means",
        "",
        markdown_table(
            [
                {"group": "baseline_positive", **groups["baseline_positive"]},
                {"group": "severe_positive", **groups["severe_positive"]},
                {"group": "claude_claimed", **groups["claude_claimed"]},
            ],
            [
                "group",
                "folds",
                "btc_return_pct",
                "btc_vol_72h_mean",
                "btc_h4_adx_mean",
                "btc_h4_long_share",
                "btc_h4_short_share",
                "btc_funding_mean",
            ],
        ),
        "",
        "## Severe-Positive Differentials",
        "",
        markdown_table(severe_diffs, ["metric", "selected_mean", "other_mean", "delta"]),
        "",
        "## Baseline-Positive Differentials",
        "",
        markdown_table(baseline_diffs, ["metric", "selected_mean", "other_mean", "delta"]),
        "",
        "## Claude-Claimed Fold Differentials",
        "",
        markdown_table(claude_diffs, ["metric", "selected_mean", "other_mean", "delta"]),
        "",
        "## Decision",
        "",
        "Yes, the bot can eventually choose timeframe/regime dynamically, but only",
        "through an explicit regime-permission layer that is tested out-of-sample.",
        "This diagnostic is the evidence-gathering step for that layer.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostic-only fold regime analysis for volatility breakout research.")
    parser.add_argument("--selected-json", default="volatility_breakout_v1_report.json")
    parser.add_argument("--results", default="volatility_breakout_v1_results.csv")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--claude-folds", nargs="*", type=int, default=list(DEFAULT_CLAUDE_FOLDS))
    parser.add_argument("--json-out", default="volatility_breakout_regime_diagnostics.json")
    parser.add_argument("--md-out", default="docs/VOLATILITY_BREAKOUT_REGIME_DIAGNOSTICS_2026_05_05.md")
    args = parser.parse_args()

    report = build_report(
        selected_path=args.selected_json,
        results_path=args.results,
        years=args.years,
        claude_folds=tuple(int(value) for value in args.claude_folds),
    )
    Path(args.json_out).write_text(json.dumps(risk_metrics.rounded_nested(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(report, args.md_out)
    print(json.dumps(risk_metrics.rounded_nested({"status": report["status"], "current_run_positive_folds": report["current_run_positive_folds"]}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

