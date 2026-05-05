from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd

import carry_research
from hurst_mtf_momentum_report import (
    SCENARIOS,
    UNIVERSE,
    _fold_ranges,
    _score,
    _scenario_cost_rate,
    contribution_share,
    crisis_alpha,
    fetch_ohlcv_history,
    make_exchange,
    markdown_table,
    resample_ohlcv,
    stitch_equity,
    tail_capture,
)
import pbo_report
import risk_metrics
import vol_target_sizing
import volatility_breakout_signal as signal


@dataclass(frozen=True)
class Candidate:
    breakout_lookback: int
    squeeze_lookback: int
    squeeze_pctile_max: float
    volume_z_min: float
    h4_adx_min: float
    target_vol: float
    min_breakout_atr: float = 0.05
    max_chase_atr: float = 1.50
    min_range_atr: float = 2.0
    btc_vol_72h_max: float = 999.0
    btc_h4_adx_max: float = 999.0
    btc_abs_shock_max: float = 4.0
    btc_funding_abs_max: float = 999.0

    @property
    def name(self) -> str:
        name = (
            f"BO{self.breakout_lookback}|SQ{self.squeeze_lookback}-{self.squeeze_pctile_max:.2f}|"
            f"VZ{self.volume_z_min:.1f}|ADX{self.h4_adx_min:.0f}|TV{self.target_vol:.2f}"
        )
        if self.btc_vol_72h_max < 900.0 or self.btc_h4_adx_max < 900.0 or self.btc_funding_abs_max < 900.0:
            name = (
                f"{name}|BV{self.btc_vol_72h_max:.2f}|"
                f"BADX{self.btc_h4_adx_max:.0f}|BS{self.btc_abs_shock_max:.1f}|"
                f"BF{self.btc_funding_abs_max:.5f}"
            )
        return name


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
    h1_atr: np.ndarray
    h1_volume_z: np.ndarray
    h4_side: np.ndarray
    h4_adx: np.ndarray
    daily_side: np.ndarray
    btc_side: np.ndarray
    btc_shock_z: np.ndarray
    btc_vol_72h: np.ndarray
    btc_h4_adx: np.ndarray
    btc_funding_rate: np.ndarray
    realized_vol_30d: np.ndarray
    breakout_high: dict[int, np.ndarray]
    breakout_low: dict[int, np.ndarray]
    breakout_range_atr: dict[int, np.ndarray]
    breakout_up_atr: dict[int, np.ndarray]
    breakout_down_atr: dict[int, np.ndarray]
    breakout_up: dict[int, np.ndarray]
    breakout_down: dict[int, np.ndarray]
    recent_squeeze: dict[int, np.ndarray]


@dataclass
class BacktestData:
    index: pd.DatetimeIndex
    symbols: tuple[str, ...]
    by_symbol: dict[str, FeatureArrays]


def _log_progress(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[vol-breakout] {time.strftime('%Y-%m-%d %H:%M:%S')} {message}", file=sys.stderr, flush=True)


def _float_array(features: pd.DataFrame, column: str) -> np.ndarray:
    if column not in features:
        return np.full(len(features), np.nan, dtype="float64")
    return pd.to_numeric(features[column], errors="coerce").to_numpy(dtype="float64")


def _funding_rate_per_1h(scenario: dict[str, float]) -> float:
    import config

    return float(getattr(config, "DEFAULT_FUNDING_RATE_PER_8H", 0.0001)) * float(scenario.get("funding_mult", 1.0)) / 8.0


def prepare_symbol(
    symbol: str,
    df_1h: pd.DataFrame,
    btc_1h: pd.DataFrame,
    *,
    btc_funding: pd.DataFrame | None = None,
) -> PreparedSymbol:
    df_1h = df_1h.sort_index()
    btc_1h = btc_1h.sort_index()
    df_4h = resample_ohlcv(df_1h, "4h")
    df_1d = resample_ohlcv(df_1h, "1D")
    features = signal.build_signal_frame(df_1h=df_1h, df_4h=df_4h, df_1d=df_1d, btc_1h=btc_1h)
    if btc_funding is not None and not btc_funding.empty and "funding_rate" in btc_funding:
        funding = pd.to_numeric(btc_funding["funding_rate"], errors="coerce")
        funding.index = pd.to_datetime(funding.index, utc=True)
        features["btc_funding_rate"] = funding.sort_index().reindex(features.index, method="ffill").fillna(0.0)
    else:
        features["btc_funding_rate"] = 0.0
    features["symbol"] = symbol
    return PreparedSymbol(symbol=symbol, df_1h=df_1h, df_4h=df_4h, df_1d=df_1d, features=features)


def generate_candidates(max_candidates: int | None = None, *, regime_v2: bool = False) -> list[Candidate]:
    breakout_lookbacks = (72,) if regime_v2 else signal.BREAKOUT_LOOKBACKS
    squeeze_lookbacks = signal.SQUEEZE_LOOKBACKS
    squeeze_pctiles = (0.15, 0.25) if regime_v2 else (0.15, 0.25, 0.35)
    volume_z_values = (1.2, 1.8) if regime_v2 else (0.8, 1.2, 1.8)
    h4_adx_values = (15.0, 20.0)
    target_vol_values = (0.45,) if regime_v2 else (0.45, 0.60)
    btc_vol_values = (0.45, 0.55) if regime_v2 else (999.0,)
    btc_h4_adx_values = (26.0, 30.0) if regime_v2 else (999.0,)
    btc_abs_shock_values = (3.0, 4.0) if regime_v2 else (4.0,)
    btc_funding_abs_values = (0.00012, 0.00020) if regime_v2 else (999.0,)
    rows = [
        Candidate(
            breakout_lookback=breakout_lookback,
            squeeze_lookback=squeeze_lookback,
            squeeze_pctile_max=squeeze_pctile_max,
            volume_z_min=volume_z_min,
            h4_adx_min=h4_adx_min,
            target_vol=target_vol,
            btc_vol_72h_max=btc_vol_72h_max,
            btc_h4_adx_max=btc_h4_adx_max,
            btc_abs_shock_max=btc_abs_shock_max,
            btc_funding_abs_max=btc_funding_abs_max,
        )
        for breakout_lookback in breakout_lookbacks
        for squeeze_lookback in squeeze_lookbacks
        for squeeze_pctile_max in squeeze_pctiles
        for volume_z_min in volume_z_values
        for h4_adx_min in h4_adx_values
        for target_vol in target_vol_values
        for btc_vol_72h_max in btc_vol_values
        for btc_h4_adx_max in btc_h4_adx_values
        for btc_abs_shock_max in btc_abs_shock_values
        for btc_funding_abs_max in btc_funding_abs_values
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


def build_backtest_data(prepared: dict[str, PreparedSymbol], index: pd.DatetimeIndex) -> BacktestData:
    symbols: list[str] = []
    by_symbol: dict[str, FeatureArrays] = {}
    for symbol_name, payload in prepared.items():
        features = payload.features.reindex(index)
        breakout_high: dict[int, np.ndarray] = {}
        breakout_low: dict[int, np.ndarray] = {}
        breakout_range_atr: dict[int, np.ndarray] = {}
        breakout_up_atr: dict[int, np.ndarray] = {}
        breakout_down_atr: dict[int, np.ndarray] = {}
        breakout_up: dict[int, np.ndarray] = {}
        breakout_down: dict[int, np.ndarray] = {}
        for lookback in signal.BREAKOUT_LOOKBACKS:
            prefix = f"bo{int(lookback)}"
            breakout_high[lookback] = _float_array(features, f"{prefix}_high")
            breakout_low[lookback] = _float_array(features, f"{prefix}_low")
            breakout_range_atr[lookback] = _float_array(features, f"{prefix}_range_atr")
            breakout_up_atr[lookback] = _float_array(features, f"{prefix}_up_atr")
            breakout_down_atr[lookback] = _float_array(features, f"{prefix}_down_atr")
            breakout_up[lookback] = _float_array(features, f"{prefix}_breakout_up")
            breakout_down[lookback] = _float_array(features, f"{prefix}_breakout_down")
        recent_squeeze = {
            squeeze_lookback: _float_array(features, f"sq{int(squeeze_lookback)}_recent_squeeze")
            for squeeze_lookback in signal.SQUEEZE_LOOKBACKS
        }
        symbols.append(symbol_name)
        by_symbol[symbol_name] = FeatureArrays(
            symbol=symbol_name,
            entry_open=_float_array(features, "entry_open"),
            entry_high=_float_array(features, "entry_high"),
            entry_low=_float_array(features, "entry_low"),
            entry_close=_float_array(features, "entry_close"),
            h1_atr=_float_array(features, "h1_atr"),
            h1_volume_z=_float_array(features, "h1_volume_z"),
            h4_side=_float_array(features, "h4_side"),
            h4_adx=_float_array(features, "h4_adx"),
            daily_side=_float_array(features, "daily_side"),
            btc_side=_float_array(features, "btc_side"),
            btc_shock_z=_float_array(features, "btc_shock_z"),
            btc_vol_72h=_float_array(features, "btc_vol_72h"),
            btc_h4_adx=_float_array(features, "btc_h4_adx"),
            btc_funding_rate=_float_array(features, "btc_funding_rate"),
            realized_vol_30d=_float_array(features, "realized_vol_30d"),
            breakout_high=breakout_high,
            breakout_low=breakout_low,
            breakout_range_atr=breakout_range_atr,
            breakout_up_atr=breakout_up_atr,
            breakout_down_atr=breakout_down_atr,
            breakout_up=breakout_up,
            breakout_down=breakout_down,
            recent_squeeze=recent_squeeze,
        )
    return BacktestData(index=index, symbols=tuple(symbols), by_symbol=by_symbol)


def candidate_signal_sides(data: BacktestData, candidate: Candidate) -> dict[str, np.ndarray]:
    signals: dict[str, np.ndarray] = {}
    breakout_lookback = int(candidate.breakout_lookback)
    squeeze_lookback = int(candidate.squeeze_lookback)
    for symbol_name in data.symbols:
        arrays = data.by_symbol[symbol_name]
        side = np.zeros(len(data.index), dtype="int8")
        base_ok = (
            (arrays.recent_squeeze[squeeze_lookback] <= float(candidate.squeeze_pctile_max))
            & (arrays.h1_volume_z >= float(candidate.volume_z_min))
            & (arrays.h4_adx >= float(candidate.h4_adx_min))
            & (arrays.breakout_range_atr[breakout_lookback] >= float(candidate.min_range_atr))
            & (np.abs(arrays.btc_shock_z) <= float(candidate.btc_abs_shock_max))
            & (arrays.btc_vol_72h <= float(candidate.btc_vol_72h_max))
            & (arrays.btc_h4_adx <= float(candidate.btc_h4_adx_max))
            & (np.abs(arrays.btc_funding_rate) <= float(candidate.btc_funding_abs_max))
        )
        long_ok = (
            base_ok
            & (arrays.breakout_up[breakout_lookback] == 1.0)
            & (arrays.breakout_up_atr[breakout_lookback] >= float(candidate.min_breakout_atr))
            & (arrays.breakout_up_atr[breakout_lookback] <= float(candidate.max_chase_atr))
            & (arrays.h4_side == 1.0)
            & (arrays.btc_side >= 0.0)
            & (arrays.daily_side >= 0.0)
        )
        short_ok = (
            base_ok
            & (arrays.breakout_down[breakout_lookback] == 1.0)
            & (arrays.breakout_down_atr[breakout_lookback] >= float(candidate.min_breakout_atr))
            & (arrays.breakout_down_atr[breakout_lookback] <= float(candidate.max_chase_atr))
            & (arrays.h4_side == -1.0)
            & (arrays.btc_side <= 0.0)
            & (arrays.daily_side <= 0.0)
        )
        side[long_ok & ~short_ok] = 1
        side[short_ok & ~long_ok] = -1
        signals[symbol_name] = side
    return signals


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
    funding_rate_per_1h: float,
) -> dict[str, Any]:
    bars_held = max(int(position.get("bars_held", 0)), 1)
    gross_pnl = _unrealized(position, float(exit_price))
    entry_cost = float(position.get("entry_cost", 0.0))
    exit_cost = float(position["notional"]) * float(round_trip_cost_rate) / 2.0
    funding = float(position["notional"]) * float(funding_rate_per_1h) * bars_held
    pnl_after_entry = gross_pnl - exit_cost - funding
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
        "balance_delta": round(float(pnl_after_entry), 4),
        "bars_held": bars_held,
        "reached_1r": bool(position.get("reached_1r", False)),
    }


def _metrics_1h(trades: pd.DataFrame, equity: pd.DataFrame, *, start_balance: float) -> dict[str, Any]:
    metrics = risk_metrics.equity_metrics(equity, start_balance=start_balance, timeframe="1h")
    gains = pd.to_numeric(trades.get("pnl", pd.Series(dtype=float)), errors="coerce")
    profit = float(gains[gains > 0].sum()) if not gains.empty else 0.0
    loss = abs(float(gains[gains < 0].sum())) if not gains.empty else 0.0
    metrics["trades"] = int(len(trades))
    metrics["profit_factor"] = profit / loss if loss > 0.0 else (profit if profit > 0.0 else 0.0)
    metrics["win_rate_pct"] = float((gains > 0.0).mean() * 100.0) if len(gains) else 0.0
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
    atr_stop_mult: float = 2.0,
    atr_trail_mult: float = 1.5,
    time_stop_bars: int = 36,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    scenario = scenario or SCENARIOS["baseline"]
    round_trip_cost_rate = _scenario_cost_rate(scenario)
    funding_rate = _funding_rate_per_1h(scenario)
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
        for symbol_name in data.symbols:
            close = float(data.by_symbol[symbol_name].entry_close[offset])
            if math.isfinite(close):
                current_closes[symbol_name] = close

        for symbol_name, position in list(positions.items()):
            arrays = data.by_symbol[symbol_name]
            high = float(arrays.entry_high[offset])
            low = float(arrays.entry_low[offset])
            close = float(arrays.entry_close[offset])
            atr_value = float(arrays.h1_atr[offset])
            if not (math.isfinite(high) and math.isfinite(low) and math.isfinite(close)):
                continue
            atr = max(atr_value if math.isfinite(atr_value) else float(position.get("entry_atr", 0.0)), float(position.get("entry", 1.0)) * 1e-6)
            position["bars_held"] = int(position.get("bars_held", 0)) + 1
            exit_price: float | None = None
            exit_reason = ""
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
                    funding_rate_per_1h=funding_rate,
                )
                balance += float(trade["balance_delta"])
                trade["balance"] = round(float(balance), 4)
                trades.append(trade)
                positions.pop(symbol_name, None)

        equity_now = balance
        for symbol_name, position in positions.items():
            close = current_closes.get(symbol_name)
            if close is not None:
                equity_now += _unrealized(position, close)
        equity_rows.append({"timestamp": ts, "equity": equity_now, "open_positions": len(positions)})

        for symbol_name in data.symbols:
            if len(positions) >= int(max_concurrent) or symbol_name in positions:
                continue
            side_value = int(candidate_signals[symbol_name][offset])
            if side_value == 0:
                continue
            arrays = data.by_symbol[symbol_name]
            entry = float(arrays.entry_open[offset])
            atr = float(arrays.h1_atr[offset])
            realized_vol = float(arrays.realized_vol_30d[offset])
            if not math.isfinite(entry) or not math.isfinite(atr) or not math.isfinite(realized_vol) or entry <= 0.0 or atr <= 0.0:
                continue
            notional = vol_target_sizing.position_notional(
                equity=max(equity_now, 0.0),
                realized_vol=realized_vol,
                target_vol=candidate.target_vol,
                leverage_cap=leverage_cap,
                per_position_max_pct=per_position_max_pct,
            )
            if notional <= 0.0:
                continue
            entry_cost = notional * round_trip_cost_rate / 2.0
            balance -= entry_cost
            side = "long" if side_value == 1 else "short"
            risk_distance = float(atr_stop_mult) * atr
            positions[symbol_name] = {
                "symbol": symbol_name,
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

        if balance <= 0.0:
            break

    if positions and stop > start:
        last_ts = data.index[stop - 1]
        for symbol_name, position in list(positions.items()):
            close = current_closes.get(symbol_name, float(position["entry"]))
            trade = _close_trade(
                position,
                exit_time=last_ts,
                exit_price=float(close),
                reason="end_of_sample",
                round_trip_cost_rate=round_trip_cost_rate,
                funding_rate_per_1h=funding_rate,
            )
            balance += float(trade["balance_delta"])
            trade["balance"] = round(float(balance), 4)
            trades.append(trade)

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows)
    if not equity_df.empty:
        equity_df["timestamp"] = pd.to_datetime(equity_df["timestamp"], utc=True)
        equity_df = equity_df.set_index("timestamp")
    metrics = _metrics_1h(trades_df, equity_df, start_balance=start_balance)
    return trades_df, equity_df, metrics


def strict_gate_summary_1h(
    *,
    severe_trades: pd.DataFrame,
    severe_equity: pd.DataFrame,
    fold_rows: pd.DataFrame,
    matrix: pd.DataFrame,
    candidate_count: int,
    start_balance: float,
) -> dict[str, Any]:
    metrics = risk_metrics.equity_metrics(severe_equity, start_balance=start_balance, timeframe="1h")
    pbo = pbo_report.build_pbo_report(matrix) if not matrix.empty else {"folds": 0, "pbo": 1.0}
    days = (severe_equity.index.max() - severe_equity.index.min()).total_seconds() / 86400.0 if len(severe_equity) > 1 else 0.0
    years = max(days / 365.0, 1.0 / 365.0)
    dsr = risk_metrics.multiple_testing_sharpe_haircut(
        sharpe=float(metrics.get("sharpe", 0.0)),
        years=years,
        test_count=max(int(candidate_count), 1),
    )
    positive_folds = int((pd.to_numeric(fold_rows.get("total_return_pct", pd.Series(dtype=float)), errors="coerce") > 0.0).sum())
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
    train_bars: int = 9600,
    test_bars: int = 1200,
    min_train_trades: int = 30,
    start_balance: float = 5000.0,
    leverage_cap: float = 10.0,
    per_position_max_pct: float = 0.20,
    max_concurrent: int = 4,
    purge_bars: int = 36,
    embargo_bars: int = 0,
    progress: bool = False,
    progress_every_candidates: int = 24,
) -> dict[str, Any]:
    index = common_feature_index(prepared)
    ranges = _fold_ranges(index, train_bars=train_bars, test_bars=test_bars, folds=folds, purge_bars=purge_bars, embargo_bars=embargo_bars)
    backtest_data = build_backtest_data(prepared, index)
    signal_cache: dict[Candidate, dict[str, np.ndarray]] = {}
    matrix_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    scenario_rows: list[dict[str, Any]] = []
    severe_trades: list[pd.DataFrame] = []
    severe_equity_frames: list[pd.DataFrame] = []
    started_at = time.monotonic()
    _log_progress(progress, f"walk-forward start symbols={len(backtest_data.symbols)} candidates={len(candidates)} folds={len(ranges)} bars={len(index)}")

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
            _train_trades, _train_equity, train_metrics = _run_candidate_backtest_arrays(
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
            _test_trades, _test_equity, test_metrics = _run_candidate_backtest_arrays(
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
                    "breakout_lookback": int(candidate.breakout_lookback),
                    "squeeze_lookback": int(candidate.squeeze_lookback),
                    "squeeze_pctile_max": round(float(candidate.squeeze_pctile_max), 6),
                    "volume_z_min": round(float(candidate.volume_z_min), 6),
                    "h4_adx_min": round(float(candidate.h4_adx_min), 6),
                    "target_vol": round(float(candidate.target_vol), 6),
                    "btc_vol_72h_max": round(float(candidate.btc_vol_72h_max), 6),
                    "btc_h4_adx_max": round(float(candidate.btc_h4_adx_max), 6),
                    "btc_abs_shock_max": round(float(candidate.btc_abs_shock_max), 6),
                    "btc_funding_abs_max": round(float(candidate.btc_funding_abs_max), 8),
                    "selected": False,
                }
            )
            if int(progress_every_candidates) > 0 and (
                candidate_number % int(progress_every_candidates) == 0 or candidate_number == len(candidates)
            ):
                _log_progress(progress, f"fold {period}/{len(ranges)} candidates {candidate_number}/{len(candidates)} elapsed={time.monotonic() - started_at:.1f}s")

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
                "breakout_lookback": int(selected.breakout_lookback),
                "squeeze_lookback": int(selected.squeeze_lookback),
                "squeeze_pctile_max": round(float(selected.squeeze_pctile_max), 6),
                "volume_z_min": round(float(selected.volume_z_min), 6),
                "h4_adx_min": round(float(selected.h4_adx_min), 6),
                "target_vol": round(float(selected.target_vol), 6),
                "btc_vol_72h_max": round(float(selected.btc_vol_72h_max), 6),
                "btc_h4_adx_max": round(float(selected.btc_h4_adx_max), 6),
                "btc_abs_shock_max": round(float(selected.btc_abs_shock_max), 6),
                "btc_funding_abs_max": round(float(selected.btc_funding_abs_max), 8),
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
                "breakout_lookback": int(selected.breakout_lookback),
                "squeeze_lookback": int(selected.squeeze_lookback),
                "squeeze_pctile_max": round(float(selected.squeeze_pctile_max), 6),
                "volume_z_min": round(float(selected.volume_z_min), 6),
                "h4_adx_min": round(float(selected.h4_adx_min), 6),
                "target_vol": round(float(selected.target_vol), 6),
                "btc_vol_72h_max": round(float(selected.btc_vol_72h_max), 6),
                "btc_h4_adx_max": round(float(selected.btc_h4_adx_max), 6),
                "btc_abs_shock_max": round(float(selected.btc_abs_shock_max), 6),
                "btc_funding_abs_max": round(float(selected.btc_funding_abs_max), 8),
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
    strict = strict_gate_summary_1h(
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


def write_markdown(report: dict[str, Any], path: str | Path, *, command: str) -> None:
    strict = report["strict"]
    selected = report["selected"].to_dict(orient="records") if not report["selected"].empty else []
    scenarios = report["scenarios"].to_dict(orient="records") if not report["scenarios"].empty else []
    checks = [{"gate": key, "pass": value} for key, value in strict["checks"].items()]
    is_v2 = "V2" in str(path).upper()
    title = "Volatility Breakout V2 Regime Gate Report - 2026-05-05" if is_v2 else "Volatility Breakout V1 Report - 2026-05-05"
    method = [
        "Methodology: fixed 8-perp universe, 1h entries, recent Bollinger-bandwidth",
        "squeeze, volume-confirmed 1h range breakout, 4h trend/ADX alignment, BTC",
        "market-leader direction gate, 12-fold train/test walk-forward, purge gap,",
        "severe cost stress, PBO matrix, concentration, tail-capture, and crisis-alpha checks.",
    ]
    if is_v2:
        method.extend(
            [
                "V2 keeps the V1 signal family but adds BTC regime-permission gates:",
                "BTC 72h volatility max, BTC 4h ADX max, BTC shock max, and BTC",
                "absolute funding max. If a gate fails, the candidate stays flat.",
            ]
        )
    lines = [
        f"# {title}",
        "",
        "Status: research-only. This does not enable paper, testnet, or live execution.",
        "",
        f"Command: `{command}`",
        "",
        f"Strict status: `{strict['status']}`",
        "",
        *method,
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
                "btc_vol_72h_max",
                "btc_h4_adx_max",
                "btc_abs_shock_max",
                "btc_funding_abs_max",
            ],
        ),
        "",
        "## Scenario Folds",
        "",
        markdown_table(
            scenarios,
            [
                "period",
                "scenario",
                "candidate",
                "trades",
                "total_return_pct",
                "max_dd_pct",
                "sortino",
                "profit_factor",
                "btc_vol_72h_max",
                "btc_h4_adx_max",
                "btc_abs_shock_max",
                "btc_funding_abs_max",
            ],
        ),
        "",
        "## Decision",
        "",
        "Phase B is allowed only if every strict gate is true. If status is",
        "`benchmark_only`, this candidate stays research-only and should not be",
        "connected to paper or live execution.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only volatility breakout walk-forward report.")
    parser.add_argument("--symbols", nargs="*", default=list(UNIVERSE))
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--folds", type=int, default=12)
    parser.add_argument("--train-bars", type=int, default=9600)
    parser.add_argument("--test-bars", type=int, default=1200)
    parser.add_argument("--start-balance", type=float, default=5000.0)
    parser.add_argument("--leverage-cap", type=float, default=10.0)
    parser.add_argument("--per-position-max-pct", type=float, default=0.20)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--purge-bars", type=int, default=36)
    parser.add_argument("--embargo-bars", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--regime-v2", action="store_true", help="Enable V2 BTC regime-permission candidate grid.")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--progress-every-candidates", type=int, default=24)
    parser.add_argument("--out", default="volatility_breakout_v1_results.csv")
    parser.add_argument("--matrix-out", default="volatility_breakout_v1_pbo_matrix.csv")
    parser.add_argument("--trades-out", default="volatility_breakout_v1_trades.csv")
    parser.add_argument("--json-out", default="volatility_breakout_v1_report.json")
    parser.add_argument("--md-out", default="docs/VOLATILITY_BREAKOUT_V1_REPORT_2026_05_05.md")
    args = parser.parse_args()
    progress = not bool(args.quiet)

    exchange = make_exchange()
    days = max(30, int(float(args.years) * 365.0))
    raw: dict[str, pd.DataFrame] = {}
    _log_progress(progress, f"fetch start symbols={len(args.symbols)} days={days}")
    for symbol_number, symbol_name in enumerate(args.symbols, start=1):
        _log_progress(progress, f"fetch {symbol_number}/{len(args.symbols)} symbol={symbol_name}")
        df_1h = fetch_ohlcv_history(exchange, symbol_name, timeframe="1h", days=days)
        if df_1h.empty:
            _log_progress(progress, f"skip symbol={symbol_name} reason=empty_ohlcv")
            continue
        raw[symbol_name] = df_1h

    btc_symbol = "BTC/USDT:USDT"
    btc_1h = raw.get(btc_symbol)
    if btc_1h is None or btc_1h.empty:
        raise RuntimeError("BTC/USDT:USDT data is required for the BTC market-leader gate.")
    if args.regime_v2:
        try:
            btc_funding = carry_research.fetch_funding_history(exchange, btc_symbol, days=days)
            if not btc_funding.empty:
                btc_funding.index = pd.to_datetime(btc_funding.index, utc=True)
        except Exception as exc:
            _log_progress(progress, f"btc funding unavailable; using zero funding-rate gate input reason={exc}")
            btc_funding = pd.DataFrame(columns=["funding_rate"])
    else:
        btc_funding = pd.DataFrame(columns=["funding_rate"])
    prepared: dict[str, PreparedSymbol] = {}
    for symbol_name, df_1h in raw.items():
        prepared[symbol_name] = prepare_symbol(symbol_name, df_1h, btc_1h, btc_funding=btc_funding)
        _log_progress(progress, f"prepared symbol={symbol_name} bars_1h={len(df_1h)} feature_bars={len(prepared[symbol_name].features)}")

    candidates = generate_candidates(max_candidates=args.max_candidates or None, regime_v2=bool(args.regime_v2))
    if args.max_candidates:
        _log_progress(
            progress,
            f"debug max-candidates active candidates={len(candidates)} strict_full_candidates={len(generate_candidates(regime_v2=bool(args.regime_v2)))}",
        )
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
        write_markdown(report, args.md_out, command=" ".join(["python", "volatility_breakout_report.py"] + sys.argv[1:]))

    print(json.dumps(risk_metrics.rounded_nested(report["strict"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
