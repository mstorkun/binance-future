from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass
from typing import Iterator

import pandas as pd

import config
import portfolio_backtest as pb
import risk_metrics


@dataclass(frozen=True)
class PatternScenario:
    name: str
    pattern_risk_enabled: bool


DEFAULT_SCENARIOS = [
    PatternScenario("baseline_config", bool(getattr(config, "PATTERN_RISK_ENABLED", True))),
    PatternScenario("pattern_risk_off", False),
    PatternScenario("pattern_risk_on", True),
]


@contextlib.contextmanager
def temporary_pattern_risk(enabled: bool) -> Iterator[None]:
    saved = config.PATTERN_RISK_ENABLED
    config.PATTERN_RISK_ENABLED = bool(enabled)
    try:
        yield
    finally:
        config.PATTERN_RISK_ENABLED = saved


def summarize_result(name: str, trades: pd.DataFrame, equity: pd.DataFrame) -> dict:
    metrics = risk_metrics.equity_metrics(
        equity,
        start_balance=config.CAPITAL_USDT,
        timeframe=config.TIMEFRAME,
    )
    return {
        "scenario": name,
        "trades": int(len(trades)),
        "win_rate_pct": round(float((trades["pnl"] > 0).sum() / len(trades) * 100.0), 2)
        if not trades.empty else 0.0,
        "final_equity": round(metrics["final_equity"], 2),
        "total_return_pct": round(metrics["total_return_pct"], 2),
        "cagr_pct": round(metrics["cagr_pct"], 2),
        "max_dd_pct": round(metrics["max_dd_pct"], 2),
        "sharpe": round(metrics["sharpe"], 4),
        "sortino": round(metrics["sortino"], 4),
        "calmar": round(metrics["calmar"], 4),
        "commission": round(float(trades["commission"].sum()), 2) if not trades.empty else 0.0,
        "slippage": round(float(trades["slippage"].sum()), 2) if not trades.empty else 0.0,
        "funding": round(float(trades["funding"].sum()), 2) if not trades.empty else 0.0,
    }


def run_pattern_ablation(
    *,
    symbols: list[str] | None = None,
    years: int = 3,
    out: str = "pattern_ablation_results.csv",
) -> pd.DataFrame:
    symbols = symbols or list(config.SYMBOLS)
    data = pb.fetch_all_data(symbols, years=years)
    rows = []
    for scenario in DEFAULT_SCENARIOS:
        with temporary_pattern_risk(scenario.pattern_risk_enabled):
            trades, equity = pb.run_portfolio_backtest(
                symbols,
                data,
                start_balance=config.CAPITAL_USDT,
                max_concurrent=min(config.MAX_OPEN_POSITIONS, len(symbols)),
            )
        rows.append(summarize_result(scenario.name, trades, equity))
    result = pd.DataFrame(rows)
    if out:
        result.to_csv(out, index=False)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pattern-risk on/off ablation.")
    parser.add_argument("--symbols", nargs="*", default=None)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--out", default="pattern_ablation_results.csv")
    args = parser.parse_args()

    result = run_pattern_ablation(symbols=args.symbols, years=args.years, out=args.out)
    print(result.to_string(index=False))
    print(f"Output: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
