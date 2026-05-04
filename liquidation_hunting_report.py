from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd

import config
import risk_metrics


DEFAULT_SYMBOLS = ["DOGE/USDT:USDT", "LINK/USDT:USDT", "TRX/USDT:USDT"]
DEFAULT_TIMEFRAMES = ["5m", "15m"]


def make_exchange() -> ccxt.Exchange:
    return ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})


def ohlcv_to_df(raw: list[list[float]]) -> pd.DataFrame:
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    if df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp").astype(float)


def fetch_ohlcv_history(
    exchange: ccxt.Exchange,
    symbol: str,
    *,
    timeframe: str = "5m",
    days: int = 90,
    limit: int = 1000,
) -> pd.DataFrame:
    since = exchange.milliseconds() - int(days * 24 * 60 * 60 * 1000)
    rows: list[list[float]] = []
    while since < exchange.milliseconds():
        batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        if not batch:
            break
        rows.extend(batch)
        last_ts = int(batch[-1][0])
        if last_ts <= since or len(batch) < limit:
            break
        since = last_ts + 1
    return ohlcv_to_df(rows)


def add_liquidation_proxy_features(
    df: pd.DataFrame,
    *,
    volume_window: int = 96,
    range_window: int = 96,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy().sort_index()
    out["return_pct"] = (out["close"] / out["open"] - 1.0) * 100.0
    out["range_pct"] = (out["high"] / out["low"].replace(0, pd.NA) - 1.0) * 100.0
    out["upper_wick_pct"] = (out["high"] / out[["open", "close"]].max(axis=1).replace(0, pd.NA) - 1.0) * 100.0
    out["lower_wick_pct"] = (out[["open", "close"]].min(axis=1) / out["low"].replace(0, pd.NA) - 1.0) * 100.0
    vol_mean = out["volume"].rolling(int(volume_window), min_periods=max(5, int(volume_window) // 4)).mean()
    vol_std = out["volume"].rolling(int(volume_window), min_periods=max(5, int(volume_window) // 4)).std(ddof=0)
    out["volume_z"] = (out["volume"] - vol_mean) / vol_std.replace(0, pd.NA)
    out["range_ma_pct"] = out["range_pct"].rolling(int(range_window), min_periods=max(5, int(range_window) // 4)).mean()
    return out.replace([float("inf"), float("-inf")], pd.NA)


def event_signal(
    row: pd.Series,
    *,
    min_abs_return_pct: float = 0.8,
    min_volume_z: float = 2.5,
    min_range_multiple: float = 1.2,
) -> str | None:
    volume_z = row.get("volume_z")
    range_pct = row.get("range_pct")
    range_ma = row.get("range_ma_pct")
    ret = row.get("return_pct")
    if pd.isna(volume_z) or pd.isna(range_pct) or pd.isna(range_ma) or pd.isna(ret):
        return None
    if float(volume_z) < float(min_volume_z):
        return None
    if float(range_pct) < float(range_ma) * float(min_range_multiple):
        return None
    if float(ret) <= -float(min_abs_return_pct):
        return "long"
    if float(ret) >= float(min_abs_return_pct):
        return "short"
    return None


def event_indices(
    features: pd.DataFrame,
    *,
    min_abs_return_pct: float = 0.8,
    min_volume_z: float = 2.5,
    min_range_multiple: float = 1.2,
) -> list[tuple[int, str]]:
    required = {"volume_z", "range_pct", "range_ma_pct", "return_pct"}
    if features.empty or not required.issubset(features.columns):
        return []
    volume_z = pd.to_numeric(features["volume_z"], errors="coerce")
    range_pct = pd.to_numeric(features["range_pct"], errors="coerce")
    range_ma = pd.to_numeric(features["range_ma_pct"], errors="coerce")
    returns = pd.to_numeric(features["return_pct"], errors="coerce")
    base = (
        volume_z.notna()
        & range_pct.notna()
        & range_ma.notna()
        & returns.notna()
        & (volume_z >= float(min_volume_z))
        & (range_pct >= range_ma * float(min_range_multiple))
    )
    long_mask = base & (returns <= -float(min_abs_return_pct))
    short_mask = base & (returns >= float(min_abs_return_pct))
    event_mask = long_mask | short_mask
    positions = [int(pos) for pos in event_mask.to_numpy().nonzero()[0]]
    return [(pos, "long" if bool(long_mask.iloc[pos]) else "short") for pos in positions]


def conservative_exit(
    bars: pd.DataFrame,
    *,
    side: str,
    entry: float,
    tp_pct: float,
    sl_pct: float,
) -> tuple[int, float, str]:
    if side == "long":
        tp = entry * (1.0 + float(tp_pct) / 100.0)
        sl = entry * (1.0 - float(sl_pct) / 100.0)
        for offset, row in enumerate(bars.itertuples(), start=0):
            stop_hit = float(row.low) <= sl
            tp_hit = float(row.high) >= tp
            if stop_hit:
                return offset, sl, "sl"
            if tp_hit:
                return offset, tp, "tp"
        return len(bars) - 1, float(bars.iloc[-1]["close"]), "time"

    tp = entry * (1.0 - float(tp_pct) / 100.0)
    sl = entry * (1.0 + float(sl_pct) / 100.0)
    for offset, row in enumerate(bars.itertuples(), start=0):
        stop_hit = float(row.high) >= sl
        tp_hit = float(row.low) <= tp
        if stop_hit:
            return offset, sl, "sl"
        if tp_hit:
            return offset, tp, "tp"
    return len(bars) - 1, float(bars.iloc[-1]["close"]), "time"


def backtest_liquidation_proxy(
    df: pd.DataFrame,
    *,
    symbol: str = "",
    timeframe: str = "5m",
    min_abs_return_pct: float = 0.8,
    min_volume_z: float = 2.5,
    min_range_multiple: float = 1.2,
    horizon_bars: int = 12,
    tp_pct: float = 1.2,
    sl_pct: float = 0.8,
    start_balance: float = 5000.0,
    leverage: float = 7.0,
    risk_per_trade_pct: float = 0.03,
    max_margin_fraction: float = 1.0,
    round_trip_cost_rate: float | None = None,
    min_cooldown_bars: int = 6,
    max_trades_per_day: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    features = add_liquidation_proxy_features(df)
    cost_rate = float(
        round_trip_cost_rate
        if round_trip_cost_rate is not None
        else getattr(config, "ROUND_TRIP_FEE_RATE", 0.0008) + getattr(config, "SLIPPAGE_RATE_ROUND_TRIP", 0.0015)
    )
    balance = float(start_balance)
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    next_allowed_idx = 0
    trades_by_day: dict[str, int] = {}
    events = event_indices(
        features,
        min_abs_return_pct=min_abs_return_pct,
        min_volume_z=min_volume_z,
        min_range_multiple=min_range_multiple,
    )
    for event_idx, side in events:
        entry_idx = event_idx + 1
        if entry_idx <= next_allowed_idx or entry_idx >= len(features):
            continue
        exit_end = min(entry_idx + int(horizon_bars), len(features) - 1)
        if exit_end <= entry_idx:
            continue
        entry_bar = features.iloc[entry_idx]
        entry = float(entry_bar["open"])
        if entry <= 0:
            continue
        entry_day = features.index[entry_idx].date().isoformat()
        if int(max_trades_per_day) > 0 and trades_by_day.get(entry_day, 0) >= int(max_trades_per_day):
            continue
        raw_notional = balance * float(risk_per_trade_pct) / max(float(sl_pct) / 100.0, 1e-9)
        cap_notional = balance * float(max_margin_fraction) * float(leverage)
        notional = min(raw_notional, cap_notional)
        if notional <= 0:
            continue
        exit_offset, exit_price, reason = conservative_exit(
            features.iloc[entry_idx : exit_end + 1],
            side=side,
            entry=entry,
            tp_pct=tp_pct,
            sl_pct=sl_pct,
        )
        exit_idx = entry_idx + exit_offset
        signed_return = (float(exit_price) / entry - 1.0) if side == "long" else (entry / float(exit_price) - 1.0)
        gross_pnl = notional * signed_return
        cost = notional * cost_rate
        pnl = gross_pnl - cost
        balance += pnl
        event_bar = features.iloc[event_idx]
        trade = {
            "symbol": symbol,
            "timeframe": timeframe,
            "event_time": features.index[event_idx].isoformat(),
            "entry_time": features.index[entry_idx].isoformat(),
            "exit_time": features.index[exit_idx].isoformat(),
            "side": side,
            "entry": round(entry, 8),
            "exit": round(float(exit_price), 8),
            "exit_reason": reason,
            "event_return_pct": round(float(event_bar["return_pct"]), 6),
            "event_volume_z": round(float(event_bar["volume_z"]), 4),
            "event_range_pct": round(float(event_bar["range_pct"]), 6),
            "notional": round(float(notional), 4),
            "margin_used": round(float(notional) / float(leverage), 4),
            "risk_per_trade_pct": round(float(risk_per_trade_pct), 6),
            "cooldown_bars": int(min_cooldown_bars),
            "gross_pnl": round(float(gross_pnl), 4),
            "cost": round(float(cost), 4),
            "pnl": round(float(pnl), 4),
            "balance": round(float(balance), 4),
            "bars_held": int(exit_idx - entry_idx + 1),
        }
        trades.append(trade)
        equity_rows.append({"timestamp": features.index[exit_idx], "equity": balance})
        trades_by_day[entry_day] = trades_by_day.get(entry_day, 0) + 1
        next_allowed_idx = exit_idx + max(0, int(min_cooldown_bars))
        if balance <= 0:
            break
    return pd.DataFrame(trades), pd.DataFrame(equity_rows)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty or "pnl" not in trades:
        return 0.0
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").dropna()
    wins = float(pnl[pnl > 0].sum())
    losses = abs(float(pnl[pnl <= 0].sum()))
    if losses <= 0:
        return wins if wins > 0 else 0.0
    return wins / losses


def summarize_trades(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    start_balance: float = 5000.0,
    target_cagr_pct: float = 80.0,
    max_dd_limit_pct: float = 35.0,
    min_trades: int = 20,
    sample_days: float | None = None,
    min_sample_days: float = 0.0,
) -> dict[str, Any]:
    if trades.empty:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "trades": 0,
            "ok": False,
            "reason": "no_trades",
        }
    metrics = risk_metrics.equity_metrics(equity, start_balance=start_balance, timeframe=timeframe)
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0.0)
    wins = int((pnl > 0).sum())
    total = int(len(trades))
    pf = profit_factor(trades)
    observed_days = float(sample_days) if sample_days is not None else _trade_sample_days(trades)
    failures: list[str] = []
    if total < int(min_trades):
        failures.append("insufficient_trades")
    if observed_days < float(min_sample_days):
        failures.append("insufficient_sample")
    if metrics["cagr_pct"] < float(target_cagr_pct):
        failures.append("target_not_met")
    if metrics["max_dd_pct"] > float(max_dd_limit_pct):
        failures.append("drawdown_limit")
    if pf < 1.2:
        failures.append("profit_factor_low")
    ok = not failures
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "trades": total,
        "wins": wins,
        "win_rate_pct": round(wins / total * 100.0, 4),
        "total_pnl": round(float(pnl.sum()), 4),
        "final_equity": round(float(metrics["final_equity"]), 4),
        "total_return_pct": round(float(metrics["total_return_pct"]), 4),
        "cagr_pct": round(float(metrics["cagr_pct"]), 4),
        "max_dd_pct": round(float(metrics["max_dd_pct"]), 4),
        "sharpe": round(float(metrics["sharpe"]), 4),
        "profit_factor": round(float(pf), 4),
        "sample_days": round(float(observed_days), 4),
        "min_sample_days": round(float(min_sample_days), 4),
        "ok": ok,
        "reason": "" if ok else "|".join(failures),
    }


def _trade_sample_days(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    for first_col, last_col in (("entry_time", "exit_time"), ("event_time", "exit_time")):
        if first_col in trades and last_col in trades:
            first = pd.to_datetime(trades[first_col], errors="coerce", utc=True).dropna()
            last = pd.to_datetime(trades[last_col], errors="coerce", utc=True).dropna()
            if not first.empty and not last.empty:
                return max((last.max() - first.min()).total_seconds() / 86400.0, 0.0)
    return 0.0


def _data_sample_days(df: pd.DataFrame) -> float:
    if df.empty or len(df.index) < 2:
        return 0.0
    return max((df.index[-1] - df.index[0]).total_seconds() / 86400.0, 0.0)


def param_grid(*, horizon_values: list[int] | None = None) -> list[dict[str, Any]]:
    values = {
        "min_abs_return_pct": [0.9, 1.2],
        "min_volume_z": [2.5, 3.0],
        "min_range_multiple": [1.2],
        "horizon_bars": horizon_values or [6, 12, 24, 36],
        "tp_pct": [1.2, 1.8],
        "sl_pct": [0.8, 1.2],
    }
    keys = list(values)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(values[key] for key in keys))]


def score_summary(summary: dict[str, Any]) -> tuple[float, float, float, float]:
    if int(summary.get("trades", 0) or 0) <= 0:
        return (-1e9, -1e9, -1e9, 1e9)
    return (
        float(summary.get("cagr_pct", 0.0) or 0.0),
        float(summary.get("profit_factor", 0.0) or 0.0),
        float(summary.get("total_return_pct", 0.0) or 0.0),
        -float(summary.get("max_dd_pct", 0.0) or 0.0),
    )


def train_test_split(df: pd.DataFrame, *, train_ratio: float = 0.6) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df.copy(), df.copy()
    split = max(1, min(len(df) - 1, int(len(df) * float(train_ratio))))
    return df.iloc[:split].copy(), df.iloc[split:].copy()


def evaluate_symbol_timeframe(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    start_balance: float = 5000.0,
    leverage: float = 7.0,
    risk_per_trade_pct: float = 0.03,
    min_cooldown_bars: int = 6,
    max_trades_per_day: int = 4,
    horizon_values: list[int] | None = None,
    target_cagr_pct: float = 80.0,
    max_dd_limit_pct: float = 35.0,
    min_trades: int = 20,
    min_test_days: float = 30.0,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    train, test = train_test_split(df, train_ratio=0.6)
    candidates: list[dict[str, Any]] = []
    for params in param_grid(horizon_values=horizon_values):
        trades, equity = backtest_liquidation_proxy(
            train,
            symbol=symbol,
            timeframe=timeframe,
            start_balance=start_balance,
            leverage=leverage,
            risk_per_trade_pct=risk_per_trade_pct,
            min_cooldown_bars=min_cooldown_bars,
            max_trades_per_day=max_trades_per_day,
            **params,
        )
        summary = summarize_trades(
            trades,
            equity,
            symbol=symbol,
            timeframe=timeframe,
            start_balance=start_balance,
            target_cagr_pct=target_cagr_pct,
            max_dd_limit_pct=max_dd_limit_pct,
            min_trades=max(5, min_trades // 2),
            sample_days=_data_sample_days(train),
            min_sample_days=0.0,
        )
        candidates.append({**summary, **params})
    best = sorted(candidates, key=score_summary, reverse=True)[0] if candidates else {}
    selected_params = {key: best[key] for key in ("min_abs_return_pct", "min_volume_z", "min_range_multiple", "horizon_bars", "tp_pct", "sl_pct") if key in best}
    test_trades, test_equity = backtest_liquidation_proxy(
        test,
        symbol=symbol,
        timeframe=timeframe,
        start_balance=start_balance,
        leverage=leverage,
        risk_per_trade_pct=risk_per_trade_pct,
        min_cooldown_bars=min_cooldown_bars,
        max_trades_per_day=max_trades_per_day,
        **selected_params,
    )
    test_summary = summarize_trades(
        test_trades,
        test_equity,
        symbol=symbol,
        timeframe=timeframe,
        start_balance=start_balance,
        target_cagr_pct=target_cagr_pct,
        max_dd_limit_pct=max_dd_limit_pct,
        min_trades=min_trades,
        sample_days=_data_sample_days(test),
        min_sample_days=min_test_days,
    )
    result = {
        **test_summary,
        "train_best_cagr_pct": best.get("cagr_pct", 0.0),
        "train_best_trades": best.get("trades", 0),
        "train_best_profit_factor": best.get("profit_factor", 0.0),
        "start_balance": float(start_balance),
        "leverage": float(leverage),
        "risk_per_trade_pct": float(risk_per_trade_pct),
        "min_cooldown_bars": int(min_cooldown_bars),
        "max_trades_per_day": int(max_trades_per_day),
        "target_net_cagr_pct": float(target_cagr_pct),
        "min_test_days": float(min_test_days),
        "selected_params": json.dumps(selected_params, sort_keys=True),
    }
    return result, test_trades, test_equity


def scan_symbols(
    symbols: list[str],
    *,
    timeframes: list[str],
    days: int = 90,
    start_balance: float = 5000.0,
    leverage: float = 7.0,
    risk_per_trade_pct: float = 0.03,
    risk_per_trade_pcts: list[float] | None = None,
    min_cooldown_bars: int = 6,
    max_trades_per_day: int = 4,
    horizon_values: list[int] | None = None,
    target_cagr_pct: float = 80.0,
    max_dd_limit_pct: float = 35.0,
    min_trades: int = 20,
    min_test_days: float = 30.0,
    exchange: ccxt.Exchange | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exchange = exchange or make_exchange()
    summaries: list[dict[str, Any]] = []
    all_trades: list[pd.DataFrame] = []
    risk_values = risk_per_trade_pcts if risk_per_trade_pcts is not None else [risk_per_trade_pct]
    for symbol in symbols:
        for timeframe in timeframes:
            df = fetch_ohlcv_history(exchange, symbol, timeframe=timeframe, days=days)
            if df.empty:
                for risk_value in risk_values:
                    summaries.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "risk_per_trade_pct": float(risk_value),
                        "start_balance": float(start_balance),
                        "leverage": float(leverage),
                        "target_net_cagr_pct": float(target_cagr_pct),
                        "min_test_days": float(min_test_days),
                        "trades": 0,
                        "ok": False,
                        "reason": "no_ohlcv_data",
                    })
                continue
            for risk_value in risk_values:
                summary, trades, _equity = evaluate_symbol_timeframe(
                    df,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_balance=start_balance,
                    leverage=leverage,
                    risk_per_trade_pct=float(risk_value),
                    min_cooldown_bars=min_cooldown_bars,
                    max_trades_per_day=max_trades_per_day,
                    horizon_values=horizon_values,
                    target_cagr_pct=target_cagr_pct,
                    max_dd_limit_pct=max_dd_limit_pct,
                    min_trades=min_trades,
                    min_test_days=min_test_days,
                )
                summary["bars"] = int(len(df))
                summaries.append(summary)
                if not trades.empty:
                    all_trades.append(trades)
    result = pd.DataFrame(summaries)
    if not result.empty:
        result = result.sort_values(
            ["ok", "cagr_pct", "profit_factor", "total_return_pct"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True)
    trades_out = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    return result, trades_out


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


def write_markdown(result: pd.DataFrame, path: str | Path, *, command: str, target_cagr_pct: float) -> None:
    pass_count = int(result["ok"].sum()) if "ok" in result.columns else 0
    rows = result.head(12).to_dict(orient="records") if not result.empty else []
    columns = [
        "symbol",
        "timeframe",
        "risk_per_trade_pct",
        "trades",
        "total_return_pct",
        "cagr_pct",
        "max_dd_pct",
        "profit_factor",
        "sample_days",
        "ok",
        "reason",
    ]
    lines = [
        "# Liquidation Hunting Proxy PoC - 2026-05-04",
        "",
        "This is a research-only high-return strategy lab report. It uses public",
        "Binance Futures OHLCV as a liquidation proxy: large directional candle,",
        "large volume z-score, and expanded range. It does not use private",
        "Coinglass/Coinalyze liquidation feeds yet, does not place orders, and does",
        "not change paper/testnet/live behavior.",
        "",
        "## Method",
        "",
        "Parameters are selected on the train slice and then applied to the held-out",
        "test slice. Entries happen on the next bar open after a closed proxy event.",
        "If TP and SL are both touched inside the same candle, the backtest assumes",
        "the stop is hit first. A cooldown and per-day trade cap are applied so the",
        "research does not reward high churn that only pays commission.",
        "",
        f"Target gate: net CAGR >= `{target_cagr_pct}%` after modeled fees/slippage,",
        "profit factor >= `1.2`, enough trades, and max drawdown within the",
        "configured limit. Short annualized samples are blocked by a minimum OOS",
        "sample-days gate. Capital amount is not the success metric; percentage",
        "return after costs is.",
        "",
        f"Command: `{command}`",
        "",
        "## Result",
        "",
        f"- Rows: `{len(result)}`",
        f"- Passing rows: `{pass_count}`",
        "",
        markdown_table(rows, columns),
        "",
        "## Decision",
        "",
        "A pass here would only justify a stricter second pass with real liquidation",
        "feed data and walk-forward folds. If pass count is zero, do not promote this",
        "strategy to paper/live.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only liquidation hunting proxy report.")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframes", nargs="*", default=DEFAULT_TIMEFRAMES)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--start-balance", type=float, default=5000.0)
    parser.add_argument("--leverage", type=float, default=7.0)
    parser.add_argument("--risk-per-trade-pct", type=float, default=0.03)
    parser.add_argument("--risk-grid", nargs="*", type=float, default=None)
    parser.add_argument("--min-cooldown-bars", type=int, default=6)
    parser.add_argument("--max-trades-per-day", type=int, default=4)
    parser.add_argument("--horizon-grid", nargs="*", type=int, default=None)
    parser.add_argument("--target-cagr-pct", type=float, default=80.0)
    parser.add_argument("--max-dd-limit-pct", type=float, default=35.0)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--min-test-days", type=float, default=30.0)
    parser.add_argument("--out", default="liquidation_hunting_results.csv")
    parser.add_argument("--trades-out", default="liquidation_hunting_trades.csv")
    parser.add_argument("--json-out", default="liquidation_hunting_report.json")
    parser.add_argument("--md-out", default="docs/LIQUIDATION_HUNTING_2026_05_04.md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    risk_values = args.risk_grid if args.risk_grid else [args.risk_per_trade_pct]
    result, trades = scan_symbols(
        args.symbols,
        timeframes=args.timeframes,
        days=args.days,
        start_balance=args.start_balance,
        leverage=args.leverage,
        risk_per_trade_pct=args.risk_per_trade_pct,
        risk_per_trade_pcts=risk_values,
        min_cooldown_bars=args.min_cooldown_bars,
        max_trades_per_day=args.max_trades_per_day,
        horizon_values=args.horizon_grid,
        target_cagr_pct=args.target_cagr_pct,
        max_dd_limit_pct=args.max_dd_limit_pct,
        min_trades=args.min_trades,
        min_test_days=args.min_test_days,
    )
    if args.out:
        result.to_csv(args.out, index=False)
    if args.trades_out:
        trades.to_csv(args.trades_out, index=False)
    if args.json_out:
        payload = {"summary": result.to_dict(orient="records"), "trades": trades.to_dict(orient="records")}
        Path(args.json_out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = "python liquidation_hunting_report.py " + " ".join(
        [
            "--symbols " + " ".join(args.symbols),
            "--timeframes " + " ".join(args.timeframes),
            f"--days {args.days}",
            f"--start-balance {args.start_balance:g}",
            f"--leverage {args.leverage:g}",
            "--risk-grid " + " ".join(f"{risk:g}" for risk in risk_values),
            f"--min-cooldown-bars {args.min_cooldown_bars}",
            f"--max-trades-per-day {args.max_trades_per_day}",
            "--horizon-grid " + " ".join(str(horizon) for horizon in (args.horizon_grid or [6, 12, 24, 36])),
            f"--target-cagr-pct {args.target_cagr_pct:g}",
            f"--min-test-days {args.min_test_days:g}",
        ]
    )
    if args.md_out:
        write_markdown(result, args.md_out, command=command, target_cagr_pct=args.target_cagr_pct)
    if args.json:
        print(json.dumps(result.to_dict(orient="records"), indent=2, sort_keys=True))
    else:
        print(result.to_string(index=False))
        if args.out:
            print(f"Output: {args.out}")
        if args.md_out:
            print(f"Markdown: {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
