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

import htf_reversion_signal as signal
from hurst_mtf_momentum_report import (
    SCENARIOS,
    UNIVERSE,
    _fold_ranges,
    _funding_rate_per_4h,
    _metrics,
    _score,
    _scenario_cost_rate,
    fetch_ohlcv_history,
    make_exchange,
    markdown_table,
    resample_ohlcv,
    stitch_equity,
    strict_gate_summary,
)
import risk_metrics
import vol_target_sizing


@dataclass(frozen=True)
class Candidate:
    level_lookback: int
    rsi_low: float
    rsi_high: float
    max_adx: float
    touch_atr_mult: float
    max_reclaim_atr: float
    target_vol: float
    volume_z_min: float
    avoid_daily_opposite: bool
    min_range_atr: float = 3.0

    @property
    def name(self) -> str:
        daily = "AVD1" if self.avoid_daily_opposite else "AVD0"
        return (
            f"LB{self.level_lookback}|RSI{self.rsi_low:.0f}-{self.rsi_high:.0f}|"
            f"ADX{self.max_adx:.0f}|T{self.touch_atr_mult:.2f}|"
            f"R{self.max_reclaim_atr:.1f}|TV{self.target_vol:.2f}|"
            f"VZ{self.volume_z_min:.1f}|{daily}"
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
    h4_rsi: np.ndarray
    h4_adx: np.ndarray
    h4_volume_z: np.ndarray
    daily_side: np.ndarray
    realized_vol_30d: np.ndarray
    support: dict[int, np.ndarray]
    resistance: dict[int, np.ndarray]
    support_gap_atr: dict[int, np.ndarray]
    support_reclaim_atr: dict[int, np.ndarray]
    resistance_gap_atr: dict[int, np.ndarray]
    resistance_reclaim_atr: dict[int, np.ndarray]
    range_width_atr: dict[int, np.ndarray]


@dataclass
class BacktestData:
    index: pd.DatetimeIndex
    symbols: tuple[str, ...]
    by_symbol: dict[str, FeatureArrays]


LEVEL_LOOKBACKS = (60, 120, 180)


def _log_progress(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[htf-reversion] {time.strftime('%Y-%m-%d %H:%M:%S')} {message}", file=sys.stderr, flush=True)


def _float_array(features: pd.DataFrame, column: str) -> np.ndarray:
    if column not in features:
        return np.full(len(features), np.nan, dtype="float64")
    return pd.to_numeric(features[column], errors="coerce").to_numpy(dtype="float64")


def prepare_symbol(symbol: str, df_1h: pd.DataFrame, *, level_lookbacks: tuple[int, ...] = LEVEL_LOOKBACKS) -> PreparedSymbol:
    df_1h = df_1h.sort_index()
    df_4h = resample_ohlcv(df_1h, "4h")
    df_1d = resample_ohlcv(df_1h, "1D")
    features = signal.build_signal_frame(df_1d=df_1d, df_4h=df_4h, level_lookbacks=level_lookbacks)
    features["symbol"] = symbol
    return PreparedSymbol(symbol=symbol, df_1h=df_1h, df_4h=df_4h, df_1d=df_1d, features=features)


def generate_candidates(max_candidates: int | None = None) -> list[Candidate]:
    rows = [
        Candidate(
            level_lookback=level_lookback,
            rsi_low=rsi_low,
            rsi_high=rsi_high,
            max_adx=max_adx,
            touch_atr_mult=touch_atr_mult,
            max_reclaim_atr=max_reclaim_atr,
            target_vol=target_vol,
            volume_z_min=volume_z_min,
            avoid_daily_opposite=avoid_daily_opposite,
        )
        for level_lookback in LEVEL_LOOKBACKS
        for rsi_low, rsi_high in ((25.0, 75.0), (30.0, 70.0), (35.0, 65.0))
        for max_adx in (18.0, 22.0, 26.0)
        for touch_atr_mult in (0.0, 0.25, 0.50)
        for max_reclaim_atr in (1.5,)
        for target_vol in (0.35, 0.50)
        for volume_z_min in (0.0, 1.0)
        for avoid_daily_opposite in (True,)
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
    for symbol, payload in prepared.items():
        features = payload.features.reindex(index)
        support: dict[int, np.ndarray] = {}
        resistance: dict[int, np.ndarray] = {}
        support_gap_atr: dict[int, np.ndarray] = {}
        support_reclaim_atr: dict[int, np.ndarray] = {}
        resistance_gap_atr: dict[int, np.ndarray] = {}
        resistance_reclaim_atr: dict[int, np.ndarray] = {}
        range_width_atr: dict[int, np.ndarray] = {}
        for lookback in LEVEL_LOOKBACKS:
            prefix = f"lb{int(lookback)}"
            support[lookback] = _float_array(features, f"{prefix}_support")
            resistance[lookback] = _float_array(features, f"{prefix}_resistance")
            support_gap_atr[lookback] = _float_array(features, f"{prefix}_support_gap_atr")
            support_reclaim_atr[lookback] = _float_array(features, f"{prefix}_support_reclaim_atr")
            resistance_gap_atr[lookback] = _float_array(features, f"{prefix}_resistance_gap_atr")
            resistance_reclaim_atr[lookback] = _float_array(features, f"{prefix}_resistance_reclaim_atr")
            range_width_atr[lookback] = _float_array(features, f"{prefix}_range_width_atr")
        symbols.append(symbol)
        by_symbol[symbol] = FeatureArrays(
            symbol=symbol,
            entry_open=_float_array(features, "entry_open"),
            entry_high=_float_array(features, "entry_high"),
            entry_low=_float_array(features, "entry_low"),
            entry_close=_float_array(features, "entry_close"),
            h4_atr=_float_array(features, "h4_atr"),
            h4_rsi=_float_array(features, "h4_rsi"),
            h4_adx=_float_array(features, "h4_adx"),
            h4_volume_z=_float_array(features, "h4_volume_z"),
            daily_side=_float_array(features, "daily_side"),
            realized_vol_30d=_float_array(features, "realized_vol_30d"),
            support=support,
            resistance=resistance,
            support_gap_atr=support_gap_atr,
            support_reclaim_atr=support_reclaim_atr,
            resistance_gap_atr=resistance_gap_atr,
            resistance_reclaim_atr=resistance_reclaim_atr,
            range_width_atr=range_width_atr,
        )
    return BacktestData(index=index, symbols=tuple(symbols), by_symbol=by_symbol)


def candidate_signal_sides(data: BacktestData, candidate: Candidate) -> dict[str, np.ndarray]:
    signals: dict[str, np.ndarray] = {}
    lookback = int(candidate.level_lookback)
    for symbol in data.symbols:
        arrays = data.by_symbol[symbol]
        side = np.zeros(len(data.index), dtype="int8")
        adx_ok = arrays.h4_adx <= float(candidate.max_adx)
        volume_ok = arrays.h4_volume_z >= float(candidate.volume_z_min)
        range_ok = arrays.range_width_atr[lookback] >= float(candidate.min_range_atr)
        base_ok = adx_ok & volume_ok & range_ok
        if candidate.avoid_daily_opposite:
            long_daily_ok = arrays.daily_side >= 0.0
            short_daily_ok = arrays.daily_side <= 0.0
        else:
            long_daily_ok = np.ones(len(data.index), dtype=bool)
            short_daily_ok = np.ones(len(data.index), dtype=bool)
        long_ok = (
            base_ok
            & long_daily_ok
            & (arrays.h4_rsi <= float(candidate.rsi_low))
            & (arrays.support_gap_atr[lookback] <= float(candidate.touch_atr_mult))
            & (arrays.support_reclaim_atr[lookback] >= 0.0)
            & (arrays.support_reclaim_atr[lookback] <= float(candidate.max_reclaim_atr))
        )
        short_ok = (
            base_ok
            & short_daily_ok
            & (arrays.h4_rsi >= float(candidate.rsi_high))
            & (arrays.resistance_gap_atr[lookback] <= float(candidate.touch_atr_mult))
            & (arrays.resistance_reclaim_atr[lookback] >= 0.0)
            & (arrays.resistance_reclaim_atr[lookback] <= float(candidate.max_reclaim_atr))
        )
        side[long_ok & ~short_ok] = 1
        side[short_ok & ~long_ok] = -1
        signals[symbol] = side
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
    funding_rate_per_4h: float,
) -> dict[str, Any]:
    bars_held = max(int(position.get("bars_held", 0)), 1)
    gross_pnl = _unrealized(position, float(exit_price))
    entry_cost = float(position.get("entry_cost", 0.0))
    exit_cost = float(position["notional"]) * float(round_trip_cost_rate) / 2.0
    funding = float(position["notional"]) * float(funding_rate_per_4h) * bars_held
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
        "support": round(float(position.get("support", float("nan"))), 8),
        "resistance": round(float(position.get("resistance", float("nan"))), 8),
    }


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
    stop_atr_mult: float = 1.50,
    take_profit_atr_mult: float = 1.50,
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
            high = float(arrays.entry_high[offset])
            low = float(arrays.entry_low[offset])
            close = float(arrays.entry_close[offset])
            if not (math.isfinite(high) and math.isfinite(low) and math.isfinite(close)):
                continue
            position["bars_held"] = int(position.get("bars_held", 0)) + 1
            exit_price: float | None = None
            exit_reason = ""
            if position["side"] == "long":
                stop_level = float(position["hard_stop"])
                take_profit = float(position["take_profit"])
                if low <= stop_level:
                    exit_price = stop_level
                    exit_reason = "hard_stop"
                elif high >= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"
            else:
                stop_level = float(position["hard_stop"])
                take_profit = float(position["take_profit"])
                if high >= stop_level:
                    exit_price = stop_level
                    exit_reason = "hard_stop"
                elif low <= take_profit:
                    exit_price = take_profit
                    exit_reason = "take_profit"
            if exit_price is None and int(position.get("bars_held", 0)) >= int(time_stop_bars):
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
            lookback = int(candidate.level_lookback)
            entry = float(arrays.entry_open[offset])
            atr = float(arrays.h4_atr[offset])
            realized_vol = float(arrays.realized_vol_30d[offset])
            support = float(arrays.support[lookback][offset])
            resistance = float(arrays.resistance[lookback][offset])
            if (
                not math.isfinite(entry)
                or not math.isfinite(atr)
                or not math.isfinite(realized_vol)
                or not math.isfinite(support)
                or not math.isfinite(resistance)
                or entry <= 0.0
                or atr <= 0.0
            ):
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
            if side == "long":
                hard_stop = support - float(stop_atr_mult) * atr
                target_by_atr = entry + float(take_profit_atr_mult) * atr
                target_by_level = resistance - 0.10 * atr
                take_profit = min(target_by_atr, target_by_level) if target_by_level > entry else target_by_atr
            else:
                hard_stop = resistance + float(stop_atr_mult) * atr
                target_by_atr = entry - float(take_profit_atr_mult) * atr
                target_by_level = support + 0.10 * atr
                take_profit = max(target_by_atr, target_by_level) if target_by_level < entry else target_by_atr
            positions[symbol] = {
                "symbol": symbol,
                "entry_time": ts,
                "side": side,
                "entry": float(entry),
                "entry_atr": float(atr),
                "support": float(support),
                "resistance": float(resistance),
                "hard_stop": float(hard_stop),
                "take_profit": float(take_profit),
                "notional": float(notional),
                "entry_cost": float(entry_cost),
                "bars_held": 0,
            }

        if balance <= 0.0:
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
    )


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
    progress_every_candidates: int = 24,
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
        f"walk-forward start symbols={len(backtest_data.symbols)} candidates={len(candidates)} folds={len(ranges)} bars={len(index)}",
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
                    "level_lookback": int(candidate.level_lookback),
                    "rsi_low": round(float(candidate.rsi_low), 6),
                    "rsi_high": round(float(candidate.rsi_high), 6),
                    "max_adx": round(float(candidate.max_adx), 6),
                    "touch_atr_mult": round(float(candidate.touch_atr_mult), 6),
                    "max_reclaim_atr": round(float(candidate.max_reclaim_atr), 6),
                    "target_vol": round(float(candidate.target_vol), 6),
                    "volume_z_min": round(float(candidate.volume_z_min), 6),
                    "avoid_daily_opposite": bool(candidate.avoid_daily_opposite),
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
                "level_lookback": int(selected.level_lookback),
                "rsi_low": round(float(selected.rsi_low), 6),
                "rsi_high": round(float(selected.rsi_high), 6),
                "max_adx": round(float(selected.max_adx), 6),
                "touch_atr_mult": round(float(selected.touch_atr_mult), 6),
                "max_reclaim_atr": round(float(selected.max_reclaim_atr), 6),
                "target_vol": round(float(selected.target_vol), 6),
                "volume_z_min": round(float(selected.volume_z_min), 6),
                "avoid_daily_opposite": bool(selected.avoid_daily_opposite),
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
                "level_lookback": int(selected.level_lookback),
                "rsi_low": round(float(selected.rsi_low), 6),
                "rsi_high": round(float(selected.rsi_high), 6),
                "max_adx": round(float(selected.max_adx), 6),
                "touch_atr_mult": round(float(selected.touch_atr_mult), 6),
                "max_reclaim_atr": round(float(selected.max_reclaim_atr), 6),
                "target_vol": round(float(selected.target_vol), 6),
                "volume_z_min": round(float(selected.volume_z_min), 6),
                "avoid_daily_opposite": bool(selected.avoid_daily_opposite),
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


def write_markdown(report: dict[str, Any], path: str | Path, *, command: str) -> None:
    strict = report["strict"]
    selected = report["selected"].to_dict(orient="records") if not report["selected"].empty else []
    scenarios = report["scenarios"].to_dict(orient="records") if not report["scenarios"].empty else []
    checks = [{"gate": key, "pass": value} for key, value in strict["checks"].items()]
    lines = [
        "# HTF Support/Resistance Reversion Report - 2026-05-05",
        "",
        "Status: research-only. This does not enable paper, testnet, or live execution.",
        "",
        f"Command: `{command}`",
        "",
        f"Strict status: `{strict['status']}`",
        "",
        "Methodology: fixed 8-perp universe, 4h entries, prior 4h support/resistance",
        "levels shifted to the next bar, RSI exhaustion, low-ADX range filter, optional",
        "volume exhaustion, 12-fold train/test walk-forward, purge gap, severe cost",
        "stress, PBO matrix, concentration, tail-capture, and crisis-alpha checks.",
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
    parser = argparse.ArgumentParser(description="Research-only HTF support/resistance mean-reversion walk-forward report.")
    parser.add_argument("--symbols", nargs="*", default=list(UNIVERSE))
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--folds", type=int, default=12)
    parser.add_argument("--train-bars", type=int, default=2400)
    parser.add_argument("--test-bars", type=int, default=300)
    parser.add_argument("--start-balance", type=float, default=5000.0)
    parser.add_argument("--leverage-cap", type=float, default=10.0)
    parser.add_argument("--per-position-max-pct", type=float, default=0.20)
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--purge-bars", type=int, default=12)
    parser.add_argument("--embargo-bars", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--progress-every-candidates", type=int, default=24)
    parser.add_argument("--out", default="htf_reversion_results.csv")
    parser.add_argument("--matrix-out", default="htf_reversion_pbo_matrix.csv")
    parser.add_argument("--trades-out", default="htf_reversion_trades.csv")
    parser.add_argument("--json-out", default="htf_reversion_report.json")
    parser.add_argument("--md-out", default="docs/HTF_REVERSION_REPORT_2026_05_05.md")
    args = parser.parse_args()
    progress = not bool(args.quiet)

    exchange = make_exchange()
    prepared: dict[str, PreparedSymbol] = {}
    days = max(30, int(float(args.years) * 365.0))
    _log_progress(progress, f"prepare start symbols={len(args.symbols)} days={days}")
    for symbol_number, symbol_name in enumerate(args.symbols, start=1):
        _log_progress(progress, f"fetch {symbol_number}/{len(args.symbols)} symbol={symbol_name}")
        df_1h = fetch_ohlcv_history(exchange, symbol_name, timeframe="1h", days=days)
        if df_1h.empty:
            _log_progress(progress, f"skip symbol={symbol_name} reason=empty_ohlcv")
            continue
        prepared[symbol_name] = prepare_symbol(symbol_name, df_1h)
        _log_progress(progress, f"prepared symbol={symbol_name} bars_1h={len(df_1h)} feature_bars={len(prepared[symbol_name].features)}")

    candidates = generate_candidates(max_candidates=args.max_candidates or None)
    if args.max_candidates:
        _log_progress(progress, f"debug max-candidates active candidates={len(candidates)} strict_full_candidates={len(generate_candidates())}")
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
        write_markdown(report, args.md_out, command=" ".join(["python", "htf_reversion_report.py"] + sys.argv[1:]))

    print(json.dumps(risk_metrics.rounded_nested(report["strict"]), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
