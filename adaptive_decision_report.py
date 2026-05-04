from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import config
import btc_market_leader
import chart_pattern_features as cpf
import liquidation_hunting_report as lhr
import multi_timeframe_candle as mtc


DEFAULT_SYMBOLS = ["DOGE/USDT:USDT", "LINK/USDT:USDT", "TRX/USDT:USDT"]
DEFAULT_CONTEXT_TIMEFRAMES = ["1h", "4h", "1d", "1w"]
DEFAULT_MARKET_SYMBOLS = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
DEFAULT_HORIZONS = [12, 24, 36]


@dataclass(frozen=True)
class AdaptiveModel:
    horizon_bars: int
    feature_columns: tuple[str, ...]
    center: dict[str, float]
    scale: dict[str, float]
    coefficients: dict[str, float]
    intercept: float

    def predict_row(self, row: pd.Series) -> float | None:
        total = float(self.intercept)
        for col in self.feature_columns:
            value = _finite_float(row.get(col), None)
            if value is None:
                return None
            total += ((value - self.center[col]) / self.scale[col]) * self.coefficients[col]
        return total


def _finite_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return pd.to_numeric(num / den.replace(0, pd.NA), errors="coerce")


def _timeframe_delta(timeframe: str) -> pd.Timedelta:
    value = str(timeframe).strip().lower()
    unit = value[-1]
    amount = int(value[:-1])
    if unit == "m":
        return pd.Timedelta(minutes=amount)
    if unit == "h":
        return pd.Timedelta(hours=amount)
    if unit == "d":
        return pd.Timedelta(days=amount)
    if unit == "w":
        return pd.Timedelta(weeks=amount)
    raise ValueError(f"Unsupported timeframe: {timeframe}")


def _true_range(df: pd.DataFrame) -> pd.Series:
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift()).abs(),
        (df["low"] - df["close"].shift()).abs(),
    ], axis=1).max(axis=1)


def add_adaptive_features(df: pd.DataFrame, *, prefix: str = "") -> pd.DataFrame:
    """Create numeric model features from closed OHLCV candles."""
    out = pd.DataFrame(index=df.index)
    open_ = pd.to_numeric(df["open"], errors="coerce")
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    close = pd.to_numeric(df["close"], errors="coerce")
    volume = pd.to_numeric(df["volume"], errors="coerce")

    candle_range = (high - low).replace(0, pd.NA)
    body = close - open_
    body_abs = body.abs()
    upper_wick = high - pd.concat([open_, close], axis=1).max(axis=1)
    lower_wick = pd.concat([open_, close], axis=1).min(axis=1) - low
    returns = close.pct_change() * 100.0
    tr = _true_range(df)
    atr = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean()
    atr_pct = _safe_div(atr, close) * 100.0

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    ema_fast_slope = ema_fast.pct_change(3) * 100.0
    ema_slow_slope = ema_slow.pct_change(6) * 100.0
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1.0 / 14.0, adjust=False).mean()
    rsi = 100.0 - (100.0 / (1.0 + gain / loss.replace(0, pd.NA)))

    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr_w = tr.ewm(alpha=1.0 / 14.0, adjust=False).mean()
    plus_di = _safe_div(100.0 * plus_dm.ewm(alpha=1.0 / 14.0, adjust=False).mean(), atr_w)
    minus_di = _safe_div(100.0 * minus_dm.ewm(alpha=1.0 / 14.0, adjust=False).mean(), atr_w)
    dx = _safe_div(100.0 * (plus_di - minus_di).abs(), plus_di + minus_di)
    adx = dx.ewm(alpha=1.0 / 14.0, adjust=False).mean()

    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_width_pct = _safe_div(4.0 * bb_std, bb_mid) * 100.0
    donchian_high = high.rolling(20).max().shift(1)
    donchian_low = low.rolling(20).min().shift(1)
    donchian_width = (donchian_high - donchian_low).replace(0, pd.NA)

    volume_median = volume.rolling(48, min_periods=12).median()
    volume_std = volume.rolling(48, min_periods=12).std(ddof=0)
    obv = (np.sign(close.diff().fillna(0.0)) * volume.fillna(0.0)).cumsum()

    p = prefix
    out[f"{p}ret_1"] = returns
    out[f"{p}ret_3"] = close.pct_change(3) * 100.0
    out[f"{p}ret_12"] = close.pct_change(12) * 100.0
    out[f"{p}realized_vol_20"] = returns.rolling(20).std()
    out[f"{p}atr_pct"] = atr_pct
    out[f"{p}body_pct"] = _safe_div(body_abs, candle_range)
    out[f"{p}body_signed_atr"] = _safe_div(body, atr)
    out[f"{p}upper_wick_pct"] = _safe_div(upper_wick, candle_range)
    out[f"{p}lower_wick_pct"] = _safe_div(lower_wick, candle_range)
    out[f"{p}close_location"] = _safe_div(close - low, candle_range)
    out[f"{p}range_atr"] = _safe_div(candle_range, atr)
    out[f"{p}ema_fast_slope"] = ema_fast_slope
    out[f"{p}ema_slow_slope"] = ema_slow_slope
    out[f"{p}ema_spread_atr"] = _safe_div(ema_fast - ema_slow, atr)
    out[f"{p}macd_hist_atr"] = _safe_div(macd_hist, atr)
    out[f"{p}macd_hist_slope"] = macd_hist.diff(3)
    out[f"{p}rsi"] = rsi
    out[f"{p}rsi_slope"] = rsi.diff(3)
    out[f"{p}adx"] = adx
    out[f"{p}di_spread"] = plus_di - minus_di
    out[f"{p}bb_width_pct"] = bb_width_pct
    out[f"{p}bb_width_z"] = (bb_width_pct - bb_width_pct.rolling(80).median()) / bb_width_pct.rolling(80).std(ddof=0).replace(0, pd.NA)
    out[f"{p}donchian_pos"] = _safe_div(close - donchian_low, donchian_width) - 0.5
    out[f"{p}donchian_width_atr"] = _safe_div(donchian_width, atr)
    out[f"{p}volume_z"] = (volume - volume_median) / volume_std.replace(0, pd.NA)
    out[f"{p}volume_ratio"] = _safe_div(volume, volume_median)
    out[f"{p}obv_slope"] = obv.diff(12) / volume.rolling(12).sum().replace(0, pd.NA)
    return out.replace([float("inf"), float("-inf")], pd.NA)


def align_context_features(
    base_index: pd.Index,
    context_df: pd.DataFrame,
    *,
    prefix: str,
    timeframe: str,
) -> pd.DataFrame:
    features = add_adaptive_features(context_df, prefix=prefix)
    features = features.join(mtc.add_candle_context_features(context_df, prefix=prefix), how="left")
    features = features.join(cpf.add_chart_pattern_features(context_df, prefix=prefix), how="left")
    features = features.copy()
    features.index = features.index + _timeframe_delta(timeframe)
    return features.reindex(base_index, method="ffill")


def build_dataset(
    base_df: pd.DataFrame,
    *,
    context_frames: dict[str, pd.DataFrame] | None = None,
    market_frames: dict[str, pd.DataFrame] | None = None,
    horizons: list[int] | None = None,
) -> pd.DataFrame:
    horizons = horizons or DEFAULT_HORIZONS
    dataset = add_adaptive_features(base_df, prefix="base_")
    dataset = dataset.join(mtc.add_candle_context_features(base_df, prefix="base_"), how="left")
    dataset = dataset.join(cpf.add_chart_pattern_features(base_df, prefix="base_"), how="left")
    context_frames = context_frames or {}
    for timeframe, frame in context_frames.items():
        dataset = dataset.join(
            align_context_features(dataset.index, frame, prefix=f"ctx_{timeframe}_", timeframe=timeframe),
            how="left",
        )
    market_frames = market_frames or {}
    base_ret = pd.to_numeric(dataset["base_ret_1"], errors="coerce")
    for name, frame in market_frames.items():
        market = add_adaptive_features(frame, prefix=f"mkt_{name}_")
        market = market.reindex(dataset.index, method="ffill")
        dataset = dataset.join(market, how="left")
        market_ret = pd.to_numeric(market[f"mkt_{name}_ret_1"], errors="coerce")
        dataset[f"corr_{name}_96"] = base_ret.rolling(96, min_periods=24).corr(market_ret)
        if name.lower() == "btc":
            leader = btc_market_leader.add_btc_leader_features(base_df, frame)
            leader_cols = [col for col in leader.columns if col.startswith("btc_")]
            dataset = dataset.join(leader[leader_cols], how="left")

    entry = pd.to_numeric(base_df["open"], errors="coerce").shift(-1)
    for horizon in horizons:
        exit_ = pd.to_numeric(base_df["close"], errors="coerce").shift(-int(horizon))
        dataset[f"target_return_{int(horizon)}"] = (exit_ / entry - 1.0) * 100.0
    return dataset.replace([float("inf"), float("-inf")], pd.NA)


def select_feature_columns(data: pd.DataFrame, *, min_valid_ratio: float = 0.55) -> list[str]:
    cols: list[str] = []
    for col in data.columns:
        if col.startswith("target_"):
            continue
        series = pd.to_numeric(data[col], errors="coerce")
        if float(series.notna().mean()) < float(min_valid_ratio):
            continue
        if series.nunique(dropna=True) < 3:
            continue
        cols.append(col)
    return cols


def train_ridge_model(
    data: pd.DataFrame,
    *,
    target_col: str,
    feature_columns: list[str],
    horizon_bars: int,
    alpha: float = 2.0,
) -> AdaptiveModel | None:
    frame = data[feature_columns + [target_col]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) < max(40, len(feature_columns) + 5):
        return None
    x = frame[feature_columns]
    y = frame[target_col]
    center = x.median()
    scale = x.std(ddof=0).replace(0, pd.NA).fillna(1.0)
    x_norm = ((x - center) / scale).to_numpy(dtype=float)
    y_arr = y.to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x_norm)), x_norm])
    penalty = np.eye(design.shape[1]) * float(alpha)
    penalty[0, 0] = 0.0
    try:
        beta = np.linalg.solve(design.T @ design + penalty, design.T @ y_arr)
    except np.linalg.LinAlgError:
        beta = np.linalg.lstsq(design.T @ design + penalty, design.T @ y_arr, rcond=None)[0]
    return AdaptiveModel(
        horizon_bars=int(horizon_bars),
        feature_columns=tuple(feature_columns),
        center={col: float(center[col]) for col in feature_columns},
        scale={col: float(scale[col]) for col in feature_columns},
        coefficients={col: float(beta[i + 1]) for i, col in enumerate(feature_columns)},
        intercept=float(beta[0]),
    )


def choose_dynamic_decision(
    predictions: dict[int, float],
    *,
    cost_pct: float,
    edge_multiplier: float = 1.5,
) -> dict[str, Any]:
    required = float(cost_pct) * float(edge_multiplier)
    best: dict[str, Any] = {"side": "wait", "horizon_bars": 0, "predicted_return_pct": 0.0, "net_edge_pct": 0.0}
    for horizon, pred in predictions.items():
        value = _finite_float(pred, None)
        if value is None:
            continue
        net_edge = abs(value) - required
        if net_edge > float(best["net_edge_pct"]):
            best = {
                "side": "long" if value > 0 else "short",
                "horizon_bars": int(horizon),
                "predicted_return_pct": float(value),
                "net_edge_pct": float(net_edge),
            }
    return best if best["net_edge_pct"] > 0 else {**best, "side": "wait"}


def dynamic_risk_fraction(
    *,
    predicted_return_pct: float,
    cost_pct: float,
    realized_vol_pct: float,
    reference_vol_pct: float,
    min_risk_pct: float = 0.01,
    max_risk_pct: float = 0.10,
) -> float:
    edge = max(abs(float(predicted_return_pct)) - float(cost_pct), 0.0)
    vol = max(float(realized_vol_pct), 1e-9)
    ref = max(float(reference_vol_pct), 1e-9)
    confidence = edge / (edge + vol)
    vol_penalty = min(1.0, ref / vol) if vol > ref else 1.0
    risk = float(min_risk_pct) + (float(max_risk_pct) - float(min_risk_pct)) * confidence * vol_penalty
    return max(float(min_risk_pct), min(float(max_risk_pct), risk))


def backtest_adaptive_decisions(
    base_df: pd.DataFrame,
    dataset: pd.DataFrame,
    models: list[AdaptiveModel],
    *,
    start_balance: float = 5000.0,
    leverage: float = 7.0,
    min_risk_pct: float = 0.01,
    max_risk_pct: float = 0.10,
    cooldown_bars: int = 6,
    edge_multiplier: float = 1.5,
    round_trip_cost_rate: float | None = None,
    enable_mtf_gate: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    cost_rate = float(
        round_trip_cost_rate
        if round_trip_cost_rate is not None
        else getattr(config, "ROUND_TRIP_FEE_RATE", 0.0008) + getattr(config, "SLIPPAGE_RATE_ROUND_TRIP", 0.0015)
    )
    cost_pct = cost_rate * 100.0
    ref_vol = float(pd.to_numeric(dataset.get("base_realized_vol_20"), errors="coerce").median() or 0.5)
    index_positions = {ts: pos for pos, ts in enumerate(base_df.index)}
    balance = float(start_balance)
    next_allowed_pos = 0
    decisions = 0
    waits = 0
    mtf_blocks = 0
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    for ts, row in dataset.iterrows():
        base_pos = index_positions.get(ts)
        if base_pos is None or base_pos <= next_allowed_pos:
            continue
        predictions = {
            model.horizon_bars: model.predict_row(row)
            for model in models
        }
        predictions = {key: value for key, value in predictions.items() if value is not None}
        decision = choose_dynamic_decision(predictions, cost_pct=cost_pct, edge_multiplier=edge_multiplier)
        decisions += 1
        if decision["side"] == "wait":
            waits += 1
            continue
        mtf_decision = mtc.multi_timeframe_candle_decision(row, side=str(decision["side"])) if enable_mtf_gate else None
        if mtf_decision is not None and mtf_decision.block_new_entries:
            mtf_blocks += 1
            waits += 1
            continue
        entry_pos = base_pos + 1
        exit_limit = min(base_pos + int(decision["horizon_bars"]), len(base_df) - 1)
        if entry_pos >= len(base_df) or exit_limit <= entry_pos:
            waits += 1
            continue
        entry = float(base_df.iloc[entry_pos]["open"])
        if entry <= 0:
            waits += 1
            continue
        vol = _finite_float(row.get("base_realized_vol_20"), ref_vol) or ref_vol
        atr_pct = _finite_float(row.get("base_atr_pct"), vol) or vol
        stop_pct = max(float(atr_pct) * 1.35, cost_pct * 2.0, 0.35)
        tp_pct = max(abs(float(decision["predicted_return_pct"])), stop_pct * 1.20, cost_pct * 3.0)
        risk_pct = dynamic_risk_fraction(
            predicted_return_pct=float(decision["predicted_return_pct"]),
            cost_pct=cost_pct,
            realized_vol_pct=float(vol),
            reference_vol_pct=ref_vol,
            min_risk_pct=min_risk_pct,
            max_risk_pct=max_risk_pct,
        )
        if mtf_decision is not None:
            risk_pct = min(float(max_risk_pct), max(0.0, risk_pct * float(mtf_decision.multiplier)))
            if risk_pct <= 0:
                mtf_blocks += 1
                waits += 1
                continue
        notional = min(
            balance * risk_pct / max(stop_pct / 100.0, 1e-9),
            balance * float(leverage),
        )
        if notional <= 0:
            waits += 1
            continue
        exit_offset, exit_price, reason = lhr.conservative_exit(
            base_df.iloc[entry_pos: exit_limit + 1],
            side=str(decision["side"]),
            entry=entry,
            tp_pct=tp_pct,
            sl_pct=stop_pct,
        )
        exit_pos = entry_pos + exit_offset
        signed_return = (float(exit_price) / entry - 1.0) if decision["side"] == "long" else (entry / float(exit_price) - 1.0)
        gross_pnl = notional * signed_return
        cost = notional * cost_rate
        pnl = gross_pnl - cost
        balance += pnl
        trades.append({
            "entry_time": base_df.index[entry_pos].isoformat(),
            "exit_time": base_df.index[exit_pos].isoformat(),
            "side": decision["side"],
            "horizon_bars": int(decision["horizon_bars"]),
            "predicted_return_pct": round(float(decision["predicted_return_pct"]), 6),
            "net_edge_pct": round(float(decision["net_edge_pct"]), 6),
            "mtf_multiplier": round(float(mtf_decision.multiplier), 6) if mtf_decision is not None else 1.0,
            "mtf_bias": mtf_decision.bias if mtf_decision is not None else "disabled",
            "mtf_confidence": round(float(mtf_decision.confidence), 6) if mtf_decision is not None else 0.0,
            "mtf_reasons": "|".join(mtf_decision.reasons) if mtf_decision is not None else "disabled",
            "risk_per_trade_pct": round(float(risk_pct), 6),
            "stop_pct": round(float(stop_pct), 6),
            "tp_pct": round(float(tp_pct), 6),
            "entry": round(entry, 8),
            "exit": round(float(exit_price), 8),
            "exit_reason": reason,
            "notional": round(float(notional), 4),
            "gross_pnl": round(float(gross_pnl), 4),
            "cost": round(float(cost), 4),
            "pnl": round(float(pnl), 4),
            "balance": round(float(balance), 4),
        })
        equity_rows.append({"timestamp": base_df.index[exit_pos], "equity": balance})
        next_allowed_pos = exit_pos + int(cooldown_bars)
        if balance <= 0:
            break

    diagnostics = {
        "decisions": int(decisions),
        "waits": int(waits),
        "wait_ratio_pct": round((waits / decisions * 100.0) if decisions else 0.0, 4),
        "mtf_blocks": int(mtf_blocks),
        "cost_pct": round(float(cost_pct), 6),
        "reference_vol_pct": round(float(ref_vol), 6),
    }
    return pd.DataFrame(trades), pd.DataFrame(equity_rows), diagnostics


def summarize_adaptive(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    diagnostics: dict[str, Any],
    *,
    symbol: str,
    timeframe: str,
    start_balance: float,
    target_cagr_pct: float,
    max_dd_limit_pct: float,
    min_trades: int,
    min_test_days: float,
    sample_days: float,
) -> dict[str, Any]:
    pnl = pd.to_numeric(trades.get("pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    final_equity = float(equity["equity"].iloc[-1]) if not equity.empty else float(start_balance)
    total_return_pct = (final_equity / float(start_balance) - 1.0) * 100.0
    years = max(float(sample_days) / 365.0, 1.0 / 365.0)
    cagr_pct = ((final_equity / float(start_balance)) ** (1.0 / years) - 1.0) * 100.0 if final_equity > 0 else -100.0
    equity_series = pd.concat([pd.Series([float(start_balance)]), pd.to_numeric(equity.get("equity", pd.Series(dtype=float)), errors="coerce")]).dropna()
    peak = equity_series.cummax()
    max_dd_pct = float(((peak - equity_series) / peak.replace(0, pd.NA)).max() * 100.0) if not equity_series.empty else 0.0
    wins = int((pnl > 0).sum())
    losses = abs(float(pnl[pnl <= 0].sum()))
    profit_factor = float(pnl[pnl > 0].sum()) / losses if losses > 0 else (float(pnl[pnl > 0].sum()) if wins else 0.0)
    failures: list[str] = []
    if len(trades) < int(min_trades):
        failures.append("insufficient_trades")
    if float(sample_days) < float(min_test_days):
        failures.append("insufficient_sample")
    if cagr_pct < float(target_cagr_pct):
        failures.append("target_not_met")
    if max_dd_pct > float(max_dd_limit_pct):
        failures.append("drawdown_limit")
    if profit_factor < 1.2:
        failures.append("profit_factor_low")
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": round((wins / len(trades) * 100.0) if len(trades) else 0.0, 4),
        "total_pnl": round(float(pnl.sum()), 4),
        "final_equity": round(final_equity, 4),
        "total_return_pct": round(total_return_pct, 4),
        "cagr_pct": round(float(cagr_pct), 4),
        "max_dd_pct": round(float(max_dd_pct), 4),
        "profit_factor": round(float(profit_factor), 4),
        "sample_days": round(float(sample_days), 4),
        **diagnostics,
        "ok": not failures,
        "reason": "" if not failures else "|".join(failures),
    }


def top_model_weights(models: list[AdaptiveModel], *, limit: int = 12) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        ranked = sorted(model.coefficients.items(), key=lambda item: abs(item[1]), reverse=True)[:limit]
        for feature, coef in ranked:
            rows.append({"horizon_bars": model.horizon_bars, "feature": feature, "coefficient": round(float(coef), 6)})
    return rows


def evaluate_symbol(
    symbol: str,
    *,
    timeframe: str,
    days: int,
    context_timeframes: list[str],
    market_symbols: list[str],
    horizons: list[int],
    start_balance: float,
    leverage: float,
    min_risk_pct: float,
    max_risk_pct: float,
    cooldown_bars: int,
    target_cagr_pct: float,
    max_dd_limit_pct: float,
    min_trades: int,
    min_test_days: float,
    enable_mtf_gate: bool = True,
    exchange=None,
) -> tuple[dict[str, Any], pd.DataFrame, list[AdaptiveModel]]:
    exchange = exchange or lhr.make_exchange()
    base = lhr.fetch_ohlcv_history(exchange, symbol, timeframe=timeframe, days=days)
    context = {
        tf: lhr.fetch_ohlcv_history(exchange, symbol, timeframe=tf, days=days)
        for tf in context_timeframes
    }
    markets = {
        name.split("/")[0].lower(): lhr.fetch_ohlcv_history(exchange, name, timeframe=timeframe, days=days)
        for name in market_symbols
    }
    if base.empty:
        return {"symbol": symbol, "timeframe": timeframe, "trades": 0, "ok": False, "reason": "no_ohlcv_data"}, pd.DataFrame(), []
    dataset = build_dataset(base, context_frames=context, market_frames=markets, horizons=horizons)
    split = max(1, min(len(dataset) - 1, int(len(dataset) * 0.60)))
    train = dataset.iloc[:split].copy()
    test = dataset.iloc[split:].copy()
    feature_cols = select_feature_columns(train)
    models: list[AdaptiveModel] = []
    for horizon in horizons:
        model = train_ridge_model(
            train,
            target_col=f"target_return_{int(horizon)}",
            feature_columns=feature_cols,
            horizon_bars=int(horizon),
        )
        if model is not None:
            models.append(model)
    if not models:
        return {"symbol": symbol, "timeframe": timeframe, "trades": 0, "ok": False, "reason": "no_model"}, pd.DataFrame(), []
    trades, equity, diagnostics = backtest_adaptive_decisions(
        base,
        test,
        models,
        start_balance=start_balance,
        leverage=leverage,
        min_risk_pct=min_risk_pct,
        max_risk_pct=max_risk_pct,
        cooldown_bars=cooldown_bars,
        enable_mtf_gate=enable_mtf_gate,
    )
    sample_days = lhr._data_sample_days(base.iloc[split:])
    summary = summarize_adaptive(
        trades,
        equity,
        diagnostics,
        symbol=symbol,
        timeframe=timeframe,
        start_balance=start_balance,
        target_cagr_pct=target_cagr_pct,
        max_dd_limit_pct=max_dd_limit_pct,
        min_trades=min_trades,
        min_test_days=min_test_days,
        sample_days=sample_days,
    )
    summary["feature_count"] = int(len(feature_cols))
    summary["model_count"] = int(len(models))
    summary["horizons"] = ",".join(str(model.horizon_bars) for model in models)
    return summary, trades, models


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "")).replace("|", "\\|") for col in columns) + " |")
    return "\n".join(lines)


def write_markdown(summary: pd.DataFrame, weights: list[dict[str, Any]], path: str | Path, *, command: str) -> None:
    rows = summary.to_dict(orient="records") if not summary.empty else []
    columns = [
        "symbol",
        "timeframe",
        "trades",
        "wait_ratio_pct",
        "total_return_pct",
        "cagr_pct",
        "max_dd_pct",
        "profit_factor",
        "sample_days",
        "ok",
        "reason",
    ]
    lines = [
        "# Adaptive Futures Decision Model - 2026-05-04",
        "",
        "Research-only report. This is not a fixed-rule indicator bot and does not",
        "place orders. Indicators, candle structure, chart-pattern structure,",
        "multi-timeframe context, market beta, correlation, and volatility are",
        "converted into numeric features.",
        "The model learns feature weights on the train slice, predicts several",
        "future horizons, then chooses long, short, or wait after modeled costs.",
        "",
        "Risk per trade is dynamic: predicted edge, cost, realized volatility, and",
        "reference volatility decide the risk fraction inside configured bounds.",
        "The multi-timeframe candle gate can block/reduce trades when weekly, daily,",
        "4h, 1h, and trigger-candle context conflict.",
        "",
        f"Command: `{command}`",
        "",
        "## Summary",
        "",
        markdown_table(rows, columns),
        "",
        "## Top Learned Weights",
        "",
        markdown_table(weights[:36], ["horizon_bars", "feature", "coefficient"]),
        "",
        "## Decision",
        "",
        "A passing row is only a research candidate. Promotion still requires",
        "walk-forward folds, PBO/DSR, slippage stress, liquidation checks, and real",
        "order-flow/OI/liquidation history.",
    ]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Research-only adaptive futures decision report.")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--context-timeframes", nargs="*", default=DEFAULT_CONTEXT_TIMEFRAMES)
    parser.add_argument("--market-symbols", nargs="*", default=DEFAULT_MARKET_SYMBOLS)
    parser.add_argument("--horizon-grid", nargs="*", type=int, default=DEFAULT_HORIZONS)
    parser.add_argument("--start-balance", type=float, default=5000.0)
    parser.add_argument("--leverage", type=float, default=7.0)
    parser.add_argument("--min-risk-pct", type=float, default=0.01)
    parser.add_argument("--max-risk-pct", type=float, default=0.10)
    parser.add_argument("--cooldown-bars", type=int, default=8)
    parser.add_argument("--target-cagr-pct", type=float, default=80.0)
    parser.add_argument("--max-dd-limit-pct", type=float, default=35.0)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--min-test-days", type=float, default=30.0)
    parser.add_argument("--disable-mtf-gate", action="store_true")
    parser.add_argument("--out", default="adaptive_decision_results.csv")
    parser.add_argument("--trades-out", default="adaptive_decision_trades.csv")
    parser.add_argument("--json-out", default="adaptive_decision_report.json")
    parser.add_argument("--md-out", default="docs/ADAPTIVE_DECISION_MODEL_2026_05_04.md")
    args = parser.parse_args()

    exchange = lhr.make_exchange()
    summaries: list[dict[str, Any]] = []
    all_trades: list[pd.DataFrame] = []
    all_weights: list[dict[str, Any]] = []
    for symbol in args.symbols:
        summary, trades, models = evaluate_symbol(
            symbol,
            timeframe=args.timeframe,
            days=args.days,
            context_timeframes=args.context_timeframes,
            market_symbols=args.market_symbols,
            horizons=args.horizon_grid,
            start_balance=args.start_balance,
            leverage=args.leverage,
            min_risk_pct=args.min_risk_pct,
            max_risk_pct=args.max_risk_pct,
            cooldown_bars=args.cooldown_bars,
            target_cagr_pct=args.target_cagr_pct,
            max_dd_limit_pct=args.max_dd_limit_pct,
            min_trades=args.min_trades,
            min_test_days=args.min_test_days,
            enable_mtf_gate=not args.disable_mtf_gate,
            exchange=exchange,
        )
        summaries.append(summary)
        if not trades.empty:
            trades = trades.copy()
            trades.insert(0, "symbol", symbol)
            all_trades.append(trades)
        all_weights.extend({"symbol": symbol, **row} for row in top_model_weights(models))

    result = pd.DataFrame(summaries)
    if not result.empty:
        result = result.sort_values(["ok", "cagr_pct", "profit_factor"], ascending=[False, False, False])
    trades_out = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if args.out:
        result.to_csv(args.out, index=False)
    if args.trades_out:
        trades_out.to_csv(args.trades_out, index=False)
    if args.json_out:
        payload = {"summary": summaries, "weights": all_weights, "trades": trades_out.to_dict(orient="records")}
        Path(args.json_out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = "python adaptive_decision_report.py " + " ".join([
        "--symbols " + " ".join(args.symbols),
        f"--timeframe {args.timeframe}",
        f"--days {args.days}",
        "--context-timeframes " + " ".join(args.context_timeframes),
        "--market-symbols " + " ".join(args.market_symbols),
        "--horizon-grid " + " ".join(str(x) for x in args.horizon_grid),
        f"--leverage {args.leverage:g}",
        f"--min-risk-pct {args.min_risk_pct:g}",
        f"--max-risk-pct {args.max_risk_pct:g}",
        f"--target-cagr-pct {args.target_cagr_pct:g}",
    ])
    if args.md_out:
        write_markdown(result, all_weights, args.md_out, command=command)
    print(result.to_string(index=False))
    if args.md_out:
        print(f"Markdown: {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
