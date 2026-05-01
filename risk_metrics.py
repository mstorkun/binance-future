from __future__ import annotations

import math
from statistics import NormalDist
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


def multiple_testing_sharpe_haircut(
    *,
    sharpe: float,
    years: float,
    test_count: int,
    alpha: float = 0.05,
) -> dict[str, Any]:
    if test_count <= 0:
        raise ValueError("test_count must be positive")
    if years <= 0:
        raise ValueError("years must be positive")
    adjusted_alpha = bonferroni_alpha(alpha, test_count)
    z_score = NormalDist().inv_cdf(1.0 - adjusted_alpha)
    standard_error = math.sqrt((1.0 + 0.5 * float(sharpe) ** 2) / float(years))
    haircut = z_score * standard_error
    lower_bound = float(sharpe) - haircut
    return {
        "method": "bonferroni_sharpe_haircut",
        "alpha": alpha,
        "test_count": int(test_count),
        "bonferroni_alpha": adjusted_alpha,
        "years": float(years),
        "sharpe": float(sharpe),
        "z_score": z_score,
        "standard_error": standard_error,
        "haircut": haircut,
        "deflated_sharpe_proxy": lower_bound,
        "passes_zero_edge_after_haircut": lower_bound > 0.0,
        "warning": "conservative_proxy_not_full_dsr",
    }


def walk_forward_overfit_summary(
    results: pd.DataFrame,
    *,
    train_col: str = "train_return_pct",
    test_col: str = "test_return_pct",
) -> dict[str, Any]:
    if results.empty:
        return {"folds": 0, "warning": "empty_results"}
    if train_col not in results.columns or test_col not in results.columns:
        raise ValueError(f"missing required columns: {train_col}, {test_col}")

    train = pd.to_numeric(results[train_col], errors="coerce")
    test = pd.to_numeric(results[test_col], errors="coerce")
    valid = pd.DataFrame({"train": train, "test": test}).dropna()
    if valid.empty:
        return {"folds": 0, "warning": "no_numeric_results"}

    positive_train = valid["train"] > 0
    degradation = pd.Series(0.0, index=valid.index)
    degradation.loc[positive_train] = 1.0 - (valid.loc[positive_train, "test"] / valid.loc[positive_train, "train"])
    severe = positive_train & (valid["test"] < valid["train"] * 0.25)
    return {
        "folds": int(len(valid)),
        "positive_test_folds": int((valid["test"] > 0).sum()),
        "negative_test_folds": int((valid["test"] <= 0).sum()),
        "test_under_train_folds": int((valid["test"] < valid["train"]).sum()),
        "severe_degradation_folds": int(severe.sum()),
        "avg_train_return_pct": float(valid["train"].mean()),
        "avg_test_return_pct": float(valid["test"].mean()),
        "median_degradation_ratio": float(degradation.median()),
        "pbo_proxy": float(severe.mean()),
        "warning": "pbo_proxy_requires_full_candidate_matrix",
    }


def rounded_metrics(metrics: dict[str, float], digits: int = 4) -> dict[str, float]:
    return {key: round(float(value), digits) for key, value in metrics.items()}


def rounded_nested(value: Any, digits: int = 4) -> Any:
    if isinstance(value, dict):
        return {key: rounded_nested(item, digits=digits) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded_nested(item, digits=digits) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value, digits)
    return value


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
