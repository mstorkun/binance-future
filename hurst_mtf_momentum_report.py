from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import ccxt
import numpy as np
import pandas as pd

import config
import hurst_gate
import mtf_momentum_signal as mtf
import pbo_report
import risk_metrics
import vol_target_sizing


UNIVERSE = (
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "DOGE/USDT:USDT",
)

SCENARIOS = {
    "baseline": {"slippage_rate": getattr(config, "SLIPPAGE_RATE_ROUND_TRIP", 0.0015), "funding_mult": 1.0},
    "slippage_30bps": {"slippage_rate": 0.0030, "funding_mult": 1.0},
    "slippage_60bps": {"slippage_rate": 0.0060, "funding_mult": 1.0},
    "funding_2x": {"slippage_rate": getattr(config, "SLIPPAGE_RATE_ROUND_TRIP", 0.0015), "funding_mult": 2.0},
    "severe": {"slippage_rate": 0.0060, "funding_mult": 2.0},
}

TRIGGER_MAX_AGE_HOURS = 4.0


@dataclass(frozen=True)
class Candidate:
    hurst_min: float
    hurst_exit: float
    adx_min: float
    volume_z_min: float
    target_vol: float

    @property
    def name(self) -> str:
        return (
            f"H{self.hurst_min:.2f}|HX{self.hurst_exit:.2f}|"
            f"ADX{self.adx_min:.0f}|VZ{self.volume_z_min:.1f}|TV{self.target_vol:.2f}"
        )


@dataclass
class PreparedSymbol:
    symbol: str
    df_1h: pd.DataFrame
    df_4h: pd.DataFrame
    df_1d: pd.DataFrame
    features: pd.DataFrame


@dataclass
class FeatureArrays:
    symbol: str
    entry_open: np.ndarray
    entry_high: np.ndarray
    entry_low: np.ndarray
    entry_close: np.ndarray
    h4_atr: np.ndarray
    h4_hurst: np.ndarray
    h4_adx: np.ndarray
    h4_ema_side: np.ndarray
    daily_side: np.ndarray
    h1_last_trigger_volume_z: np.ndarray
    h1_last_long_trigger_volume_z: np.ndarray
    h1_last_short_trigger_volume_z: np.ndarray
    h1_long_trigger_age_hours: np.ndarray
    h1_short_trigger_age_hours: np.ndarray
    realized_vol_30d: np.ndarray


@dataclass
class BacktestData:
    index: pd.DatetimeIndex
    symbols: tuple[str, ...]
    by_symbol: dict[str, FeatureArrays]


def _num(value: Any, default: float | None = 0.0) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


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
    timeframe: str = "1h",
    days: int = 365 * 3,
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


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.sort_index().resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return out.dropna(subset=["open", "high", "low", "close"])


def prepare_symbol(symbol: str, df_1h: pd.DataFrame, *, hurst_window: int = 200) -> PreparedSymbol:
    df_1h = df_1h.sort_index()
    df_4h = resample_ohlcv(df_1h, "4h")
    df_1d = resample_ohlcv(df_1h, "1D")
    close = pd.to_numeric(df_4h["close"], errors="coerce")
    returns = np.log(close / close.shift(1)).replace([float("inf"), float("-inf")], np.nan)
    hurst = hurst_gate.rolling_hurst_dfa(returns, window=int(hurst_window))
    features = mtf.build_signal_frame(df_1d=df_1d, df_4h=df_4h, df_1h=df_1h, symbol=symbol, hurst_series=hurst)
    return PreparedSymbol(symbol=symbol, df_1h=df_1h, df_4h=df_4h, df_1d=df_1d, features=features)


def generate_candidates(max_candidates: int | None = None) -> list[Candidate]:
    rows = [
        Candidate(hurst_min=hurst_min, hurst_exit=hurst_exit, adx_min=adx_min, volume_z_min=volume_z, target_vol=target_vol)
        for hurst_min in (0.53, 0.55, 0.58)
        for hurst_exit in (0.43, 0.45)
        for adx_min in (20.0, 25.0)
        for volume_z in (1.2, 1.5, 2.0)
        for target_vol in (0.45, 0.60)
    ]
    if max_candidates is not None and max_candidates > 0:
        rows = rows[: int(max_candidates)]
    return rows


def common_feature_index(prepared: dict[str, PreparedSymbol]) -> pd.DatetimeIndex:
    indexes = [payload.features.index for payload in prepared.values() if not payload.features.empty]
    if not indexes:
        return pd.DatetimeIndex([])
    common = indexes[0]
    for index in indexes[1:]:
        common = common.intersection(index)
    return common.sort_values()


def _log_progress(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[hurst-mtf] {time.strftime('%Y-%m-%d %H:%M:%S')} {message}", file=sys.stderr, flush=True)


def _float_array(features: pd.DataFrame, column: str) -> np.ndarray:
    if column not in features:
        return np.full(len(features), np.nan, dtype="float64")
    return pd.to_numeric(features[column], errors="coerce").to_numpy(dtype="float64")


def build_backtest_data(prepared: dict[str, PreparedSymbol], index: pd.DatetimeIndex) -> BacktestData:
    symbols: list[str] = []
    by_symbol: dict[str, FeatureArrays] = {}
    for symbol, payload in prepared.items():
        features = payload.features.reindex(index)
        symbols.append(symbol)
        by_symbol[symbol] = FeatureArrays(
            symbol=symbol,
            entry_open=_float_array(features, "entry_open"),
            entry_high=_float_array(features, "entry_high"),
            entry_low=_float_array(features, "entry_low"),
            entry_close=_float_array(features, "entry_close"),
            h4_atr=_float_array(features, "h4_atr"),
            h4_hurst=_float_array(features, "h4_hurst"),
            h4_adx=_float_array(features, "h4_adx"),
            h4_ema_side=_float_array(features, "h4_ema_side"),
            daily_side=_float_array(features, "daily_side"),
            h1_last_trigger_volume_z=_float_array(features, "h1_last_trigger_volume_z"),
            h1_last_long_trigger_volume_z=_float_array(features, "h1_last_long_trigger_volume_z"),
            h1_last_short_trigger_volume_z=_float_array(features, "h1_last_short_trigger_volume_z"),
            h1_long_trigger_age_hours=_float_array(features, "h1_long_trigger_age_hours"),
            h1_short_trigger_age_hours=_float_array(features, "h1_short_trigger_age_hours"),
            realized_vol_30d=_float_array(features, "realized_vol_30d"),
        )
    return BacktestData(index=index, symbols=tuple(symbols), by_symbol=by_symbol)


def candidate_signal_sides(data: BacktestData, candidate: Candidate) -> dict[str, np.ndarray]:
    signals: dict[str, np.ndarray] = {}
    for symbol in data.symbols:
        arrays = data.by_symbol[symbol]
        side = np.zeros(len(data.index), dtype="int8")
        adx_ok = arrays.h4_adx >= float(candidate.adx_min)
        hurst_ok = arrays.h4_hurst >= float(candidate.hurst_min)
        long_volume_ok = arrays.h1_last_long_trigger_volume_z >= float(candidate.volume_z_min)
        short_volume_ok = arrays.h1_last_short_trigger_volume_z >= float(candidate.volume_z_min)
        long_recent = (arrays.h1_long_trigger_age_hours >= 0.0) & (arrays.h1_long_trigger_age_hours <= TRIGGER_MAX_AGE_HOURS)
        short_recent = (arrays.h1_short_trigger_age_hours >= 0.0) & (arrays.h1_short_trigger_age_hours <= TRIGGER_MAX_AGE_HOURS)
        long_ok = (arrays.daily_side == 1.0) & (arrays.h4_ema_side == 1.0) & adx_ok & hurst_ok & long_volume_ok & long_recent
        short_ok = (arrays.daily_side == -1.0) & (arrays.h4_ema_side == -1.0) & adx_ok & hurst_ok & short_volume_ok & short_recent
        side[long_ok] = 1
        side[short_ok] = -1
        signals[symbol] = side
    return signals


def _scenario_cost_rate(scenario: dict[str, float]) -> float:
    return float(getattr(config, "ROUND_TRIP_FEE_RATE", 0.0008)) + float(scenario.get("slippage_rate", 0.0))


def _funding_rate_per_4h(scenario: dict[str, float]) -> float:
    return float(getattr(config, "DEFAULT_FUNDING_RATE_PER_8H", 0.0001)) * float(scenario.get("funding_mult", 1.0)) / 2.0


def _signal_side(row: pd.Series, candidate: Candidate) -> int:
    return mtf.signal_side_from_row(
        row,
        hurst_min=candidate.hurst_min,
        adx_min=candidate.adx_min,
        volume_z_min=candidate.volume_z_min,
    )


def _unrealized(position: dict[str, Any], close: float) -> float:
    entry = float(position["entry"])
    notional = float(position["notional"])
    if position["side"] == "long":
        return notional * (float(close) / entry - 1.0)
    return notional * (entry / float(close) - 1.0)


def _close_trade(
    position: dict[str, Any],
    *,
    exit_time: pd.Timestamp,
    exit_price: float,
    reason: str,
    round_trip_cost_rate: float,
    funding_rate_per_4h: float,
) -> dict[str, Any]:
    bars_held = max(int(position.get("bars_held", 0)), 1)
    gross_pnl = _unrealized(position, float(exit_price))
    entry_cost = float(position.get("entry_cost", 0.0))
    exit_cost = float(position["notional"]) * float(round_trip_cost_rate) / 2.0
    funding = float(position["notional"]) * float(funding_rate_per_4h) * bars_held
    pnl = gross_pnl - exit_cost - funding
    total_pnl = gross_pnl - entry_cost - exit_cost - funding
    return {
        "symbol": position["symbol"],
        "entry_time": position["entry_time"].isoformat(),
        "exit_time": exit_time.isoformat(),
        "side": position["side"],
        "entry": round(float(position["entry"]), 8),
        "exit": round(float(exit_price), 8),
        "exit_reason": reason,
        "notional": round(float(position["notional"]), 4),
        "entry_cost": round(entry_cost, 4),
        "exit_cost": round(exit_cost, 4),
        "funding": round(float(funding), 4),
        "gross_pnl": round(float(gross_pnl), 4),
        "pnl": round(float(total_pnl), 4),
        "balance_delta": round(float(pnl), 4),
        "bars_held": bars_held,
        "reached_1r": bool(position.get("reached_1r", False)),
    }


def _metrics(trades: pd.DataFrame, equity: pd.DataFrame, *, start_balance: float, timeframe: str = "4h") -> dict[str, Any]:
    metrics = risk_metrics.equity_metrics(equity, start_balance=start_balance, timeframe=timeframe)
    gains = pd.to_numeric(trades.get("pnl", pd.Series(dtype=float)), errors="coerce")
    profit = float(gains[gains > 0].sum()) if not gains.empty else 0.0
    loss = abs(float(gains[gains < 0].sum())) if not gains.empty else 0.0
    metrics["trades"] = int(len(trades))
    metrics["profit_factor"] = profit / loss if loss > 0 else (profit if profit > 0 else 0.0)
    metrics["win_rate_pct"] = float((gains > 0).mean() * 100.0) if len(gains) else 0.0
    return metrics


def _run_candidate_backtest_arrays(
    data: BacktestData,
    start: int,
    stop: int,
    candidate: Candidate,
    candidate_signals: dict[str, np.ndarray],
    *,
    start_balance: float = 5000.0,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = 0.20,
    max_concurrent: int = 4,
    scenario: dict[str, float] | None = None,
    atr_stop_mult: float = 2.5,
    atr_trail_mult: float = 1.5,
    time_stop_bars: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    scenario = scenario or SCENARIOS["baseline"]
    round_trip_cost_rate = _scenario_cost_rate(scenario)
    funding_rate = _funding_rate_per_4h(scenario)
    balance = float(start_balance)
    positions: dict[str, dict[str, Any]] = {}
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    current_closes: dict[str, float] = {}
    start = max(int(start), 0)
    stop = min(max(int(stop), start), len(data.index))

    for offset in range(start, stop):
        ts = data.index[offset]
        current_closes = {}
        for symbol in data.symbols:
            close = float(data.by_symbol[symbol].entry_close[offset])
            if math.isfinite(close):
                current_closes[symbol] = close

        for symbol, position in list(positions.items()):
            arrays = data.by_symbol[symbol]
            open_ = float(arrays.entry_open[offset])
            if not math.isfinite(open_):
                continue
            position["bars_held"] = int(position.get("bars_held", 0)) + 1
            high = float(arrays.entry_high[offset])
            low = float(arrays.entry_low[offset])
            close = float(arrays.entry_close[offset])
            atr_value = float(arrays.h4_atr[offset])
            atr = max(atr_value if math.isfinite(atr_value) else float(position.get("entry_atr", 0.0)), float(position.get("entry", 1.0)) * 1e-6)
            h4_hurst = float(arrays.h4_hurst[offset])
            if not math.isfinite(h4_hurst):
                h4_hurst = 1.0

            exit_price: float | None = None
            exit_reason = ""
            if h4_hurst < candidate.hurst_exit:
                exit_price = open_
                exit_reason = "regime_exit"
            else:
                risk_distance = float(position["risk_distance"])
                if position["side"] == "long":
                    if high >= float(position["entry"]) + risk_distance:
                        position["reached_1r"] = True
                    if position.get("reached_1r"):
                        position["trail_stop"] = max(float(position.get("trail_stop", -1e30)), high - float(atr_trail_mult) * atr)
                    stop_level = max(float(position["hard_stop"]), float(position.get("trail_stop", -1e30)))
                    if low <= stop_level:
                        exit_price = stop_level
                        exit_reason = "trailing_stop" if stop_level > float(position["hard_stop"]) else "hard_stop"
                else:
                    if low <= float(position["entry"]) - risk_distance:
                        position["reached_1r"] = True
                    if position.get("reached_1r"):
                        position["trail_stop"] = min(float(position.get("trail_stop", 1e30)), low + float(atr_trail_mult) * atr)
                    stop_level = min(float(position["hard_stop"]), float(position.get("trail_stop", 1e30)))
                    if high >= stop_level:
                        exit_price = stop_level
                        exit_reason = "trailing_stop" if stop_level < float(position["hard_stop"]) else "hard_stop"
                if exit_price is None and int(position.get("bars_held", 0)) >= int(time_stop_bars) and not position.get("reached_1r"):
                    exit_price = close
                    exit_reason = "time_stop"

            if exit_price is not None:
                trade = _close_trade(
                    position,
                    exit_time=ts,
                    exit_price=float(exit_price),
                    reason=exit_reason,
                    round_trip_cost_rate=round_trip_cost_rate,
                    funding_rate_per_4h=funding_rate,
                )
                balance += float(trade["balance_delta"])
                trade["balance"] = round(float(balance), 4)
                trades.append(trade)
                positions.pop(symbol, None)

        equity_now = balance
        for symbol, position in positions.items():
            close = current_closes.get(symbol)
            if close is not None:
                equity_now += _unrealized(position, close)
        equity_rows.append({"timestamp": ts, "equity": equity_now, "open_positions": len(positions)})

        for symbol in data.symbols:
            if len(positions) >= int(max_concurrent) or symbol in positions:
                continue
            side_value = int(candidate_signals[symbol][offset])
            if side_value == 0:
                continue
            arrays = data.by_symbol[symbol]
            entry = float(arrays.entry_open[offset])
            atr = float(arrays.h4_atr[offset])
            realized_vol = float(arrays.realized_vol_30d[offset])
            if (
                not math.isfinite(entry)
                or not math.isfinite(atr)
                or not math.isfinite(realized_vol)
                or entry <= 0
                or atr <= 0
            ):
                continue
            notional = vol_target_sizing.position_notional(
                equity=max(equity_now, 0.0),
                realized_vol=realized_vol,
                target_vol=candidate.target_vol,
                leverage_cap=leverage_cap,
                per_position_max_pct=per_position_max_pct,
            )
            if notional <= 0:
                continue
            entry_cost = notional * round_trip_cost_rate / 2.0
            balance -= entry_cost
            side = "long" if side_value == 1 else "short"
            risk_distance = float(atr_stop_mult) * atr
            positions[symbol] = {
                "symbol": symbol,
                "entry_time": ts,
                "side": side,
                "entry": float(entry),
                "entry_atr": float(atr),
                "risk_distance": float(risk_distance),
                "hard_stop": float(entry - risk_distance if side == "long" else entry + risk_distance),
                "notional": float(notional),
                "entry_cost": float(entry_cost),
                "bars_held": 0,
                "reached_1r": False,
            }

        if balance <= 0:
            break

    if positions and stop > start:
        last_ts = data.index[stop - 1]
        for symbol, position in list(positions.items()):
            close = current_closes.get(symbol, float(position["entry"]))
            trade = _close_trade(
                position,
                exit_time=last_ts,
                exit_price=float(close),
                reason="end_of_sample",
                round_trip_cost_rate=round_trip_cost_rate,
                funding_rate_per_4h=funding_rate,
            )
            balance += float(trade["balance_delta"])
            trade["balance"] = round(float(balance), 4)
            trades.append(trade)

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows)
    if not equity_df.empty:
        equity_df["timestamp"] = pd.to_datetime(equity_df["timestamp"], utc=True)
        equity_df = equity_df.set_index("timestamp")
    metrics = _metrics(trades_df, equity_df, start_balance=start_balance)
    return trades_df, equity_df, metrics


def run_candidate_backtest(
    prepared: dict[str, PreparedSymbol],
    index: pd.DatetimeIndex,
    candidate: Candidate,
    *,
    start_balance: float = 5000.0,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = 0.20,
    max_concurrent: int = 4,
    scenario: dict[str, float] | None = None,
    atr_stop_mult: float = 2.5,
    atr_trail_mult: float = 1.5,
    time_stop_bars: int = 12,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    data = build_backtest_data(prepared, index)
    signals = candidate_signal_sides(data, candidate)
    return _run_candidate_backtest_arrays(
        data,
        0,
        len(data.index),
        candidate,
        signals,
        start_balance=start_balance,
        leverage_cap=leverage_cap,
        per_position_max_pct=per_position_max_pct,
        max_concurrent=max_concurrent,
        scenario=scenario,
        atr_stop_mult=atr_stop_mult,
        atr_trail_mult=atr_trail_mult,
        time_stop_bars=time_stop_bars,
    )


def _fold_ranges(
    index: pd.DatetimeIndex,
    *,
    train_bars: int,
    test_bars: int,
    folds: int,
    purge_bars: int = 12,
    embargo_bars: int = 0,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    period = 1
    gap = max(int(purge_bars), 0) + max(int(embargo_bars), 0)
    while start + int(train_bars) + gap + int(test_bars) <= len(index) and len(rows) < int(folds):
        train_stop = start + int(train_bars)
        test_start = train_stop + gap
        test_stop = test_start + int(test_bars)
        rows.append(
            {
                "period": period,
                "train_start": start,
                "train_stop": train_stop,
                "purge_bars": max(int(purge_bars), 0),
                "embargo_bars": max(int(embargo_bars), 0),
                "test_start": test_start,
                "test_stop": test_stop,
                "train_index": index[start:train_stop],
                "test_index": index[test_start:test_stop],
            }
        )
        start += int(test_bars)
        period += 1
    return rows


def _score(metrics: dict[str, Any], *, min_train_trades: int) -> float:
    if int(metrics.get("trades", 0)) < int(min_train_trades):
        return -1_000_000.0 + int(metrics.get("trades", 0))
    dd = max(float(metrics.get("max_dd_pct", 0.0)), 2.0)
    return float(metrics.get("cagr_pct", 0.0)) / dd + float(metrics.get("sortino", 0.0)) * 5.0


def stitch_equity(equity_frames: list[pd.DataFrame], *, start_balance: float) -> pd.DataFrame:
    current = float(start_balance)
    rows: list[pd.DataFrame] = []
    for frame in equity_frames:
        if frame.empty or "equity" not in frame:
            continue
        scaled = frame.copy()
        base = float(scaled["equity"].iloc[0]) if float(scaled["equity"].iloc[0]) != 0 else float(start_balance)
        scaled["equity"] = scaled["equity"] / base * current
        current = float(scaled["equity"].iloc[-1])
        rows.append(scaled)
    if not rows:
        return pd.DataFrame(columns=["equity"])
    return pd.concat(rows).sort_index()


def contribution_share(trades: pd.DataFrame, column: str) -> float:
    if trades.empty or column not in trades or "pnl" not in trades:
        return 0.0
    pnl = pd.to_numeric(trades["pnl"], errors="coerce")
    positive_total = float(pnl[pnl > 0].sum())
    if positive_total <= 0:
        return 1.0
    grouped = trades.assign(_pnl=pnl).groupby(column)["_pnl"].sum()
    grouped = grouped[grouped > 0]
    if grouped.empty:
        return 1.0
    return float(grouped.max() / positive_total)


def tail_capture(trades: pd.DataFrame) -> float:
    if trades.empty or "pnl" not in trades:
        return 0.0
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").dropna().sort_values(ascending=False)
    positive_total = float(pnl[pnl > 0].sum())
    if positive_total <= 0:
        return 0.0
    top_n = max(1, int(math.ceil(len(pnl) * 0.05)))
    return float(pnl.head(top_n).sum() / positive_total)


def crisis_alpha(trades: pd.DataFrame, crisis_dates: tuple[str, ...] = ("2024-08-05", "2025-10-10")) -> dict[str, Any]:
    if trades.empty or "exit_time" not in trades:
        return {date: {"pnl": 0.0, "trades": 0, "ok": False} for date in crisis_dates}
    frame = trades.copy()
    frame["exit_date"] = pd.to_datetime(frame["exit_time"], utc=True).dt.date.astype(str)
    out: dict[str, Any] = {}
    for date in crisis_dates:
        rows = frame[frame["exit_date"] == date]
        pnl = float(pd.to_numeric(rows.get("pnl", pd.Series(dtype=float)), errors="coerce").sum()) if not rows.empty else 0.0
        out[date] = {"pnl": round(pnl, 4), "trades": int(len(rows)), "ok": bool(len(rows) > 0 and pnl > 0.0)}
    return out


def strict_gate_summary(
    *,
    severe_trades: pd.DataFrame,
    severe_equity: pd.DataFrame,
    fold_rows: pd.DataFrame,
    matrix: pd.DataFrame,
    candidate_count: int,
    start_balance: float,
) -> dict[str, Any]:
    metrics = risk_metrics.equity_metrics(severe_equity, start_balance=start_balance, timeframe="4h")
    pbo = pbo_report.build_pbo_report(matrix) if not matrix.empty else {"folds": 0, "pbo": 1.0}
    days = (severe_equity.index.max() - severe_equity.index.min()).total_seconds() / 86400.0 if len(severe_equity) > 1 else 0.0
    years = max(days / 365.0, 1.0 / 365.0)
    dsr = risk_metrics.multiple_testing_sharpe_haircut(
        sharpe=float(metrics.get("sharpe", 0.0)),
        years=years,
        test_count=max(int(candidate_count), 1),
    )
    positive_folds = int((pd.to_numeric(fold_rows.get("total_return_pct", pd.Series(dtype=float)), errors="coerce") > 0).sum())
    sample_trades = int(len(severe_trades))
    severe_cagr = float(metrics.get("cagr_pct", 0.0))
    sortino = float(metrics.get("sortino", 0.0))
    raw_pbo_value = pbo.get("pbo", 1.0)
    pbo_value = 1.0 if raw_pbo_value is None else float(raw_pbo_value)
    symbol_share = contribution_share(severe_trades, "symbol")
    month_frame = severe_trades.copy()
    if not month_frame.empty and "exit_time" in month_frame:
        month_frame["exit_month"] = pd.to_datetime(month_frame["exit_time"], utc=True).dt.strftime("%Y-%m")
    month_share = contribution_share(month_frame, "exit_month") if "exit_month" in month_frame else 1.0
    tail = tail_capture(severe_trades)
    crisis = crisis_alpha(severe_trades)

    checks = {
        "net_cagr_after_severe_cost_pct": severe_cagr >= 80.0,
        "pbo_below_0_30": pbo_value < 0.30,
        "walk_forward_positive_folds_7_of_12": positive_folds >= 7,
        "dsr_proxy_non_negative": float(dsr.get("deflated_sharpe_proxy", -1.0)) >= 0.0,
        "sortino_at_least_2": sortino >= 2.0,
        "no_symbol_over_40_pct_pnl": symbol_share <= 0.40,
        "no_month_over_25_pct_pnl": month_share <= 0.25,
        "tail_capture_50_to_80_pct": 0.50 <= tail <= 0.80,
        "crisis_alpha_positive": all(row.get("ok") for row in crisis.values()),
        "sample_at_least_200_trades": sample_trades >= 200,
    }
    ok = all(checks.values())
    return {
        "status": "pass" if ok else "benchmark_only",
        "ok": ok,
        "checks": checks,
        "metrics": risk_metrics.rounded_nested(metrics),
        "pbo": risk_metrics.rounded_nested(pbo),
        "dsr_proxy": risk_metrics.rounded_nested(dsr),
        "positive_folds": positive_folds,
        "folds": int(len(fold_rows)),
        "sample_trades": sample_trades,
        "symbol_pnl_share": round(float(symbol_share), 4),
        "month_pnl_share": round(float(month_share), 4),
        "tail_capture": round(float(tail), 4),
        "crisis_alpha": crisis,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def run_walk_forward(
    prepared: dict[str, PreparedSymbol],
    *,
    candidates: list[Candidate],
    folds: int = 12,
    train_bars: int = 2400,
    test_bars: int = 300,
    min_train_trades: int = 20,
    start_balance: float = 5000.0,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = 0.20,
    max_concurrent: int = 4,
    purge_bars: int = 12,
    embargo_bars: int = 0,
    progress: bool = False,
    progress_every_candidates: int = 12,
) -> dict[str, Any]:
    index = common_feature_index(prepared)
    ranges = _fold_ranges(
        index,
        train_bars=train_bars,
        test_bars=test_bars,
        folds=folds,
        purge_bars=purge_bars,
        embargo_bars=embargo_bars,
    )
    backtest_data = build_backtest_data(prepared, index)
    signal_cache: dict[Candidate, dict[str, np.ndarray]] = {}
    matrix_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    scenario_rows: list[dict[str, Any]] = []
    severe_trades: list[pd.DataFrame] = []
    severe_equity_frames: list[pd.DataFrame] = []
    started_at = time.monotonic()
    _log_progress(
        progress,
        (
            f"walk-forward start symbols={len(backtest_data.symbols)} candidates={len(candidates)} "
            f"folds={len(ranges)} bars={len(index)} purge_bars={int(purge_bars)} embargo_bars={int(embargo_bars)}"
        ),
    )

    def signals_for(candidate: Candidate) -> dict[str, np.ndarray]:
        cached = signal_cache.get(candidate)
        if cached is None:
            cached = candidate_signal_sides(backtest_data, candidate)
            signal_cache[candidate] = cached
        return cached

    for fold in ranges:
        period = int(fold["period"])
        train_start = int(fold["train_start"])
        train_stop = int(fold["train_stop"])
        test_start = int(fold["test_start"])
        test_stop = int(fold["test_stop"])
        train_index = fold["train_index"]
        test_index = fold["test_index"]
        train_results: list[dict[str, Any]] = []
        test_metrics_by_candidate: dict[Candidate, dict[str, Any]] = {}
        _log_progress(progress, f"fold {period}/{len(ranges)} train={train_index[0].isoformat()}..{train_index[-1].isoformat()} test={test_index[0].isoformat()}..{test_index[-1].isoformat()}")
        for candidate_number, candidate in enumerate(candidates, start=1):
            candidate_signals = signals_for(candidate)
            train_trades, train_equity, train_metrics = _run_candidate_backtest_arrays(
                backtest_data,
                train_start,
                train_stop,
                candidate,
                candidate_signals,
                start_balance=start_balance,
                leverage_cap=leverage_cap,
                per_position_max_pct=per_position_max_pct,
                max_concurrent=max_concurrent,
                scenario=SCENARIOS["baseline"],
            )
            score = _score(train_metrics, min_train_trades=min_train_trades)
            test_trades, test_equity, test_metrics = _run_candidate_backtest_arrays(
                backtest_data,
                test_start,
                test_stop,
                candidate,
                candidate_signals,
                start_balance=start_balance,
                leverage_cap=leverage_cap,
                per_position_max_pct=per_position_max_pct,
                max_concurrent=max_concurrent,
                scenario=SCENARIOS["baseline"],
            )
            test_metrics_by_candidate[candidate] = test_metrics
            train_results.append({"candidate": candidate, "score": score, "metrics": train_metrics})
            matrix_rows.append(
                {
                    "period": period,
                    "candidate": candidate.name,
                    "train_score": round(float(score), 6),
                    "train_return_pct": round(float(train_metrics.get("total_return_pct", 0.0)), 6),
                    "test_return_pct": round(float(test_metrics.get("total_return_pct", 0.0)), 6),
                    "train_trades": int(train_metrics.get("trades", 0)),
                    "test_trades": int(test_metrics.get("trades", 0)),
                    "selected": False,
                }
            )
            if int(progress_every_candidates) > 0 and (
                candidate_number % int(progress_every_candidates) == 0 or candidate_number == len(candidates)
            ):
                elapsed = time.monotonic() - started_at
                _log_progress(progress, f"fold {period}/{len(ranges)} candidates {candidate_number}/{len(candidates)} elapsed={elapsed:.1f}s")

        best = max(train_results, key=lambda row: float(row["score"]))
        selected: Candidate = best["candidate"]
        selected_rows.append(
            {
                "period": period,
                "candidate": selected.name,
                "train_start": train_index[0].isoformat(),
                "train_end": train_index[-1].isoformat(),
                "test_start": test_index[0].isoformat(),
                "test_end": test_index[-1].isoformat(),
                "purge_bars": int(fold.get("purge_bars", 0)),
                "embargo_bars": int(fold.get("embargo_bars", 0)),
                "train_score": round(float(best["score"]), 6),
                "train_trades": int(best["metrics"].get("trades", 0)),
                "train_return_pct": round(float(best["metrics"].get("total_return_pct", 0.0)), 6),
            }
        )
        for row in matrix_rows:
            if row["period"] == period and row["candidate"] == selected.name:
                row["selected"] = True

        _log_progress(progress, f"fold {period}/{len(ranges)} selected={selected.name} train_score={float(best['score']):.6f}")
        for scenario_name, scenario in SCENARIOS.items():
            if scenario_name == "baseline":
                trades = pd.DataFrame()
                equity = pd.DataFrame()
                metrics = test_metrics_by_candidate[selected]
            else:
                trades, equity, metrics = _run_candidate_backtest_arrays(
                    backtest_data,
                    test_start,
                    test_stop,
                    selected,
                    signals_for(selected),
                    start_balance=start_balance,
                    leverage_cap=leverage_cap,
                    per_position_max_pct=per_position_max_pct,
                    max_concurrent=max_concurrent,
                    scenario=scenario,
                )
            scenario_row = {
                "period": period,
                "scenario": scenario_name,
                "candidate": selected.name,
                "trades": int(metrics.get("trades", 0)),
                "total_return_pct": round(float(metrics.get("total_return_pct", 0.0)), 6),
                "cagr_pct": round(float(metrics.get("cagr_pct", 0.0)), 6),
                "max_dd_pct": round(float(metrics.get("max_dd_pct", 0.0)), 6),
                "sortino": round(float(metrics.get("sortino", 0.0)), 6),
                "profit_factor": round(float(metrics.get("profit_factor", 0.0)), 6),
            }
            scenario_rows.append(scenario_row)
            if scenario_name == "severe":
                if not trades.empty:
                    trades = trades.copy()
                    trades["period"] = period
                    trades["candidate"] = selected.name
                    trades["scenario"] = scenario_name
                    severe_trades.append(trades)
                if not equity.empty:
                    equity = equity.copy()
                    equity["period"] = period
                    severe_equity_frames.append(equity)
        _log_progress(progress, f"fold {period}/{len(ranges)} scenarios complete elapsed={time.monotonic() - started_at:.1f}s")

    matrix = pd.DataFrame(matrix_rows)
    selected = pd.DataFrame(selected_rows)
    scenarios = pd.DataFrame(scenario_rows)
    severe_fold_rows = scenarios[scenarios["scenario"] == "severe"].copy() if not scenarios.empty else pd.DataFrame()
    severe_trade_df = pd.concat(severe_trades, ignore_index=True) if severe_trades else pd.DataFrame()
    severe_equity = stitch_equity(severe_equity_frames, start_balance=start_balance)
    strict = strict_gate_summary(
        severe_trades=severe_trade_df,
        severe_equity=severe_equity,
        fold_rows=severe_fold_rows,
        matrix=matrix,
        candidate_count=len(candidates),
        start_balance=start_balance,
    )
    _log_progress(progress, f"walk-forward complete strict={strict['status']} elapsed={time.monotonic() - started_at:.1f}s")
    return {
        "strict": strict,
        "selected": selected,
        "scenarios": scenarios,
        "matrix": matrix,
        "severe_trades": severe_trade_df,
        "severe_equity": severe_equity,
    }


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")).replace("|", "\\|") for col in columns) + " |")
    return "\n".join(lines)


def write_markdown(report: dict[str, Any], path: str | Path, *, command: str) -> None:
    strict = report["strict"]
    selected = report["selected"].to_dict(orient="records") if not report["selected"].empty else []
    scenarios = report["scenarios"].to_dict(orient="records") if not report["scenarios"].empty else []
    checks = [{"gate": key, "pass": value} for key, value in strict["checks"].items()]
    lines = [
        "# Hurst MTF Momentum Phase A Report - 2026-05-04",
        "",
        "Status: research-only. This does not enable paper, testnet, or live execution.",
        "",
        f"Command: `{command}`",
        "",
        f"Strict status: `{strict['status']}`",
        "",
        "Methodology: fixed 8-perp universe, full 72-candidate grid unless",
        "debug-capped by CLI, 12-fold train/test walk-forward, default 12-bar",
        "purge gap before each test window, direction-specific 1h trigger volume",
        "confirmation, severe cost stress, PBO matrix, concentration, tail-capture,",
        "and crisis-alpha checks.",
        "",
        "## Strict Gates",
        "",
        markdown_table(checks, ["gate", "pass"]),
        "",
        "## Severe Metrics",
        "",
        markdown_table([strict["metrics"]], ["total_return_pct", "cagr_pct", "max_dd_pct", "sortino", "sharpe", "final_equity"]),
        "",
        "## Concentration / Tail",
        "",
        markdown_table(
            [
                {
                    "positive_folds": strict["positive_folds"],
                    "sample_trades": strict["sample_trades"],
                    "symbol_pnl_share": strict["symbol_pnl_share"],
                    "month_pnl_share": strict["month_pnl_share"],
                    "tail_capture": strict["tail_capture"],
                    "failed_checks": ",".join(strict["failed_checks"]),
                }
            ],
            ["positive_folds", "sample_trades", "symbol_pnl_share", "month_pnl_share", "tail_capture", "failed_checks"],
        ),
        "",
        "## Selected Candidates",
        "",
        markdown_table(
            selected,
            [
                "period",
                "candidate",
                "train_score",
                "train_trades",
                "train_return_pct",
                "purge_bars",
                "embargo_bars",
                "test_start",
                "test_end",
            ],
        ),
        "",
        "## Scenario Folds",
        "",
        markdown_table(scenarios, ["period", "scenario", "candidate", "trades", "total_return_pct", "max_dd_pct", "sortino", "profit_factor"]),
        "",
        "## Decision",
        "",
        "Phase B is allowed only if every strict gate is true. If status is",
        "`benchmark_only`, this candidate stays research-only and should be reviewed",
        "before any further engineering work.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only Hurst-gated MTF momentum walk-forward report.")
    parser.add_argument("--symbols", nargs="*", default=list(UNIVERSE))
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--folds", type=int, default=12)
    parser.add_argument("--train-bars", type=int, default=2400)
    parser.add_argument("--test-bars", type=int, default=300)
    parser.add_argument("--start-balance", type=float, default=5000.0)
    parser.add_argument("--leverage-cap", type=float, default=10.0)
    parser.add_argument("--per-position-max-pct", type=float, default=0.20)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--purge-bars", type=int, default=12, help="Train/test gap in 4h bars; default covers the 12-bar time stop.")
    parser.add_argument("--embargo-bars", type=int, default=0, help="Additional train/test embargo in 4h bars.")
    parser.add_argument("--max-candidates", type=int, default=0, help="Debug-only cap; omit for the strict full 72-candidate grid.")
    parser.add_argument("--quiet", action="store_true", help="Disable stderr progress logging.")
    parser.add_argument("--progress-every-candidates", type=int, default=12)
    parser.add_argument("--out", default="hurst_mtf_momentum_results.csv")
    parser.add_argument("--matrix-out", default="hurst_mtf_momentum_pbo_matrix.csv")
    parser.add_argument("--trades-out", default="hurst_mtf_momentum_trades.csv")
    parser.add_argument("--json-out", default="hurst_mtf_momentum_report.json")
    parser.add_argument("--md-out", default="docs/HURST_MTF_MOMENTUM_REPORT_2026_05_04.md")
    args = parser.parse_args()
    progress = not bool(args.quiet)

    exchange = make_exchange()
    prepared: dict[str, PreparedSymbol] = {}
    days = max(30, int(float(args.years) * 365.0))
    _log_progress(progress, f"prepare start symbols={len(args.symbols)} days={days}")
    for symbol_number, symbol in enumerate(args.symbols, start=1):
        _log_progress(progress, f"fetch {symbol_number}/{len(args.symbols)} symbol={symbol}")
        df_1h = fetch_ohlcv_history(exchange, symbol, timeframe="1h", days=days)
        if df_1h.empty:
            _log_progress(progress, f"skip symbol={symbol} reason=empty_ohlcv")
            continue
        prepared[symbol] = prepare_symbol(symbol, df_1h)
        _log_progress(progress, f"prepared symbol={symbol} bars_1h={len(df_1h)} feature_bars={len(prepared[symbol].features)}")

    candidates = generate_candidates(max_candidates=args.max_candidates or None)
    if args.max_candidates:
        _log_progress(progress, f"debug max-candidates active candidates={len(candidates)} strict_full_candidates=72")
    report = run_walk_forward(
        prepared,
        candidates=candidates,
        folds=args.folds,
        train_bars=args.train_bars,
        test_bars=args.test_bars,
        start_balance=args.start_balance,
        leverage_cap=args.leverage_cap,
        per_position_max_pct=args.per_position_max_pct,
        max_concurrent=args.max_concurrent,
        purge_bars=args.purge_bars,
        embargo_bars=args.embargo_bars,
        progress=progress,
        progress_every_candidates=args.progress_every_candidates,
    )
    if args.out:
        report["scenarios"].to_csv(args.out, index=False)
    if args.matrix_out:
        report["matrix"].to_csv(args.matrix_out, index=False)
    if args.trades_out:
        report["severe_trades"].to_csv(args.trades_out, index=False)
    if args.json_out:
        serializable = {
            "strict": report["strict"],
            "selected": report["selected"].to_dict(orient="records"),
            "scenario_rows": report["scenarios"].to_dict(orient="records"),
        }
        Path(args.json_out).write_text(json.dumps(risk_metrics.rounded_nested(serializable), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.md_out:
        write_markdown(report, args.md_out, command=" ".join(["python", "hurst_mtf_momentum_report.py"] + sys.argv[1:]))

    print(json.dumps(risk_metrics.rounded_nested(report["strict"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
