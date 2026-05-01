from __future__ import annotations

import math
from typing import Any

import pandas as pd


def periods_per_year(timeframe: str) -> float:
    value = str(timeframe).strip().lower()
    if value.endswith("m"):
        minutes = float(value[:-1])
        return 365.0 * 24.0 * 60.0 / minutes
    if value.endswith("h"):
        hours = float(value[:-1])
        return 365.0 * 24.0 / hours
    if value.endswith("d"):
        days = float(value[:-1])
        return 365.0 / days
    if value.endswith("w"):
        weeks = float(value[:-1])
        return 52.0 / weeks
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def equity_metrics(
    equity: pd.DataFrame | pd.Series,
    *,
    start_balance: float,
    timeframe: str = "4h",
    risk_free_rate: float = 0.0,
) -> dict[str, float]:
    series = _equity_series(equity)
    if series.empty:
        return _empty_metrics(start_balance)

    ppy = periods_per_year(timeframe)
    final_equity = float(series.iloc[-1])
    total_return = final_equity / start_balance - 1.0 if start_balance > 0 else 0.0
    years = max((len(series) - 1) / ppy, 1.0 / 365.0)
    cagr = (final_equity / start_balance) ** (1.0 / years) - 1.0 if start_balance > 0 and final_equity > 0 else -1.0

    returns = series.pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    annual_return = float(returns.mean()) * ppy if not returns.empty else 0.0
    annual_vol = float(returns.std(ddof=1)) * math.sqrt(ppy) if len(returns) > 1 else 0.0
    downside = returns[returns < 0]
    downside_vol = float(downside.std(ddof=1)) * math.sqrt(ppy) if len(downside) > 1 else 0.0

    peak = series.cummax()
    dd = (peak - series) / peak.where(peak != 0)
    max_dd = float(dd.max()) if not dd.empty else 0.0

    return {
        "final_equity": final_equity,
        "total_return_pct": total_return * 100.0,
        "cagr_pct": cagr * 100.0,
        "annual_return_pct": annual_return * 100.0,
        "annual_vol_pct": annual_vol * 100.0,
        "sharpe": _ratio(annual_return - risk_free_rate, annual_vol),
        "sortino": _ratio(annual_return - risk_free_rate, downside_vol),
        "max_dd_pct": max_dd * 100.0,
        "calmar": _ratio(cagr, max_dd),
    }


def bonferroni_alpha(alpha: float, test_count: int) -> float:
    if test_count <= 0:
        raise ValueError("test_count must be positive")
    if alpha <= 0 or alpha >= 1:
        raise ValueError("alpha must be between 0 and 1")
    return alpha / float(test_count)


def candidate_sweep_multiple_testing_summary(
    results: pd.DataFrame,
    *,
    alpha: float = 0.05,
    metric: str = "cagr_pct",
) -> dict[str, Any]:
    if results.empty:
        return {
            "test_count": 0,
            "alpha": alpha,
            "bonferroni_alpha": None,
            "best_metric": metric,
            "best_symbols": "",
            "best_metric_value": None,
            "warning": "empty_results",
        }
    if metric not in results.columns:
        raise ValueError(f"missing metric column: {metric}")

    values = pd.to_numeric(results[metric], errors="coerce")
    best_idx = values.idxmax()
    return {
        "test_count": int(len(results)),
        "alpha": alpha,
        "bonferroni_alpha": bonferroni_alpha(alpha, int(len(results))),
        "best_metric": metric,
        "best_symbols": str(results.loc[best_idx].get("symbols", "")),
        "best_metric_value": float(values.loc[best_idx]),
        "warning": "multiple_testing_adjustment_required",
    }


def rounded_metrics(metrics: dict[str, float], digits: int = 4) -> dict[str, float]:
    return {key: round(float(value), digits) for key, value in metrics.items()}


def _equity_series(equity: pd.DataFrame | pd.Series) -> pd.Series:
    if isinstance(equity, pd.Series):
        series = equity
    elif "equity" in equity:
        series = equity["equity"]
    else:
        return pd.Series(dtype=float)
    return pd.to_numeric(series, errors="coerce").dropna().astype(float)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0 or not math.isfinite(denominator):
        return 0.0
    return numerator / denominator


def _empty_metrics(start_balance: float) -> dict[str, float]:
    return {
        "final_equity": float(start_balance),
        "total_return_pct": 0.0,
        "cagr_pct": 0.0,
        "annual_return_pct": 0.0,
        "annual_vol_pct": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "max_dd_pct": 0.0,
        "calmar": 0.0,
    }
