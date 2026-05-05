from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from hurst_mtf_momentum_report import fetch_ohlcv_history, make_exchange, markdown_table


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _profit_factor(pnl: pd.Series) -> float | None:
    wins = float(pnl[pnl > 0].sum())
    losses = abs(float(pnl[pnl < 0].sum()))
    if losses == 0:
        return None
    return wins / losses


def build_rotation_frame(
    btc_df: pd.DataFrame,
    eth_df: pd.DataFrame,
    *,
    timeframe: str = "4h",
    lookback_bars: int = 18,
) -> pd.DataFrame:
    """Build BTC/ETH leadership features known at the next entry bar."""
    if timeframe != "4h":
        raise ValueError("market_rotation_report currently supports 4h context only")
    btc = btc_df.sort_index()
    eth = eth_df.sort_index().reindex(btc.index, method="ffill")
    btc_close = pd.to_numeric(btc["close"], errors="coerce")
    eth_close = pd.to_numeric(eth["close"], errors="coerce")
    btc_ret = btc_close.pct_change(int(lookback_bars)) * 100.0
    eth_ret = eth_close.pct_change(int(lookback_bars)) * 100.0
    out = pd.DataFrame(index=btc.index)
    out["btc_return_pct"] = btc_ret
    out["eth_return_pct"] = eth_ret
    out["eth_minus_btc_pct"] = eth_ret - btc_ret
    out["btc_realized_vol_pct"] = btc_close.pct_change().rolling(int(lookback_bars)).std() * 100.0
    out["rotation_regime"] = out.apply(classify_rotation_regime, axis=1)
    out.index = out.index + pd.Timedelta(hours=4)
    return out.replace([float("inf"), float("-inf")], pd.NA)


def classify_rotation_regime(row: pd.Series) -> str:
    btc_ret = _finite(row.get("btc_return_pct"))
    eth_ret = _finite(row.get("eth_return_pct"))
    spread = _finite(row.get("eth_minus_btc_pct"))
    if btc_ret < -2.0 and eth_ret < -2.0:
        return "risk_off_broad"
    if btc_ret > 2.0 and spread <= -0.75:
        return "btc_leads_up"
    if eth_ret > 2.0 and spread >= 0.75:
        return "eth_alt_leads_up"
    if btc_ret < -1.0 and eth_ret > btc_ret + 1.0:
        return "alt_resilient_down"
    if btc_ret > 1.0 and eth_ret < btc_ret - 1.0:
        return "btc_only_strength"
    return "mixed_neutral"


def annotate_trades(
    trades: pd.DataFrame,
    rotation: pd.DataFrame,
) -> pd.DataFrame:
    out = trades.copy()
    out["entry_time"] = pd.to_datetime(out["entry_time"], utc=True)
    context = rotation.reindex(out["entry_time"], method="ffill")
    context = context.reset_index(drop=True)
    for column in ("btc_return_pct", "eth_return_pct", "eth_minus_btc_pct", "btc_realized_vol_pct", "rotation_regime"):
        out[column] = context[column].to_numpy() if column in context else pd.NA
    out["rotation_alignment"] = out.apply(_rotation_alignment, axis=1)
    return out


def _rotation_alignment(row: pd.Series) -> str:
    side = str(row.get("side", "")).lower()
    regime = str(row.get("rotation_regime", "mixed_neutral"))
    if side == "long" and regime in {"eth_alt_leads_up", "btc_leads_up"}:
        return "with_rotation"
    if side == "short" and regime in {"risk_off_broad", "btc_only_strength"}:
        return "with_rotation"
    if side == "long" and regime == "risk_off_broad":
        return "against_rotation"
    if side == "short" and regime == "eth_alt_leads_up":
        return "against_rotation"
    return "neutral_rotation"


def summarize_frame(name: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "segment": name,
            "trades": 0,
            "win_rate_pct": 0.0,
            "pnl": 0.0,
            "mean_return_pct": 0.0,
            "profit_factor": None,
            "avg_btc_return_pct": 0.0,
            "avg_eth_minus_btc_pct": 0.0,
        }
    pnl = pd.to_numeric(frame["pnl"], errors="coerce").fillna(0.0)
    returns = pd.to_numeric(frame.get("pnl_return_pct", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    pf = _profit_factor(pnl)
    return {
        "segment": name,
        "trades": int(len(frame)),
        "win_rate_pct": round(float((pnl > 0).sum() / len(frame) * 100.0), 4),
        "pnl": round(float(pnl.sum()), 4),
        "mean_return_pct": round(float(returns.mean()), 4),
        "profit_factor": round(float(pf), 4) if pf is not None and math.isfinite(pf) else None,
        "avg_btc_return_pct": round(float(pd.to_numeric(frame["btc_return_pct"], errors="coerce").mean()), 4),
        "avg_eth_minus_btc_pct": round(float(pd.to_numeric(frame["eth_minus_btc_pct"], errors="coerce").mean()), 4),
    }


def summarize_by(annotated: pd.DataFrame, column: str) -> list[dict[str, Any]]:
    rows = [summarize_frame(str(name), frame) for name, frame in annotated.groupby(column, dropna=False)]
    return sorted(rows, key=lambda row: (-int(row["trades"]), str(row["segment"])))


def build_report(trades: pd.DataFrame, rotation: pd.DataFrame) -> dict[str, Any]:
    annotated = annotate_trades(trades, rotation)
    return {
        "status": "diagnostic_only",
        "overall": summarize_frame("all", annotated),
        "by_rotation_regime": summarize_by(annotated, "rotation_regime"),
        "by_rotation_alignment": summarize_by(annotated, "rotation_alignment"),
        "by_side_and_regime": summarize_by(
            annotated.assign(side_regime=annotated["side"].astype(str) + "|" + annotated["rotation_regime"].astype(str)),
            "side_regime",
        ),
    }


def write_markdown(report: dict[str, Any], path: str | Path, *, trades_source: str) -> None:
    columns = [
        "segment",
        "trades",
        "win_rate_pct",
        "pnl",
        "mean_return_pct",
        "profit_factor",
        "avg_btc_return_pct",
        "avg_eth_minus_btc_pct",
    ]
    lines = [
        "# Market Rotation Context Report - 2026-05-05",
        "",
        "Status: diagnostic-only. This does not change paper, testnet, or live behavior.",
        "",
        f"Source trades file: `{trades_source}`",
        "",
        "Method: annotate each trade with prior closed 4h BTC/ETH leadership context.",
        "The context is shifted to the next 4h bar to avoid lookahead.",
        "",
        "## Overall",
        "",
        markdown_table([report["overall"]], columns),
        "",
        "## Rotation Regime",
        "",
        markdown_table(report["by_rotation_regime"], columns),
        "",
        "## Rotation Alignment",
        "",
        markdown_table(report["by_rotation_alignment"], columns),
        "",
        "## Side And Regime",
        "",
        markdown_table(report["by_side_and_regime"], columns),
        "",
        "## Decision",
        "",
        "This is evidence collection only. A rotation gate can be tested in a true",
        "entry-time walk-forward only if these buckets show a stable difference after",
        "costs. It is not an execution permission and does not affect live trading.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="BTC/ETH market rotation diagnostic")
    parser.add_argument("--trades", default="portfolio_trades.csv")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--lookback-bars", type=int, default=18)
    parser.add_argument("--json-out", default="market_rotation_report.json")
    parser.add_argument("--md-out", default="docs/MARKET_ROTATION_CONTEXT_2026_05_05.md")
    args = parser.parse_args()

    exchange = make_exchange()
    days = max(1, int(float(args.years) * 365))
    btc = fetch_ohlcv_history(exchange, "BTC/USDT:USDT", timeframe=args.timeframe, days=days)
    eth = fetch_ohlcv_history(exchange, "ETH/USDT:USDT", timeframe=args.timeframe, days=days)
    rotation = build_rotation_frame(btc, eth, timeframe=args.timeframe, lookback_bars=args.lookback_bars)
    trades = pd.read_csv(args.trades)
    report = build_report(trades, rotation)
    Path(args.json_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, args.md_out, trades_source=args.trades)
    print(json.dumps(report["overall"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
