"""
Paper/testnet telemetry runner.

Default mode sends no orders. It records the same decision inputs that the live
bot uses: signal, risk multiplier, calendar/event reasons, futures flow, pattern
context, and order-book guard result. It also keeps a small virtual portfolio so
we can compare paper decisions against later live/testnet fills.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
import traceback
from pathlib import Path
from typing import Any

import ccxt
import pandas as pd

import config
import data
import execution_guard as eg
import flow_data
import indicators as ind
import liquidation
import paper_runtime
import risk as r
import strategy as strat


MIN_NOTIONAL_USDT = 100.0


def _utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, target)


def _fsync_file(handle) -> None:
    handle.flush()
    os.fsync(handle.fileno())


def _write_heartbeat(status: str, **extra: Any) -> None:
    payload = {
        "status": status,
        "updated_at": _utc_now(),
        "pid": os.getpid(),
        "run_tag": getattr(config, "PAPER_RUN_TAG", "default"),
        "timeframe": getattr(config, "TIMEFRAME", ""),
        "flow_period": getattr(config, "FLOW_PERIOD", getattr(config, "TIMEFRAME", "")),
        "scaled_lookbacks": bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False)),
        "symbols": list(getattr(config, "SYMBOLS", [])),
        **extra,
    }
    _atomic_write_json(getattr(config, "PAPER_HEARTBEAT_FILE", "paper_heartbeat.json"), payload)


def _public_exchange() -> ccxt.Exchange:
    return ccxt.binance({"options": {"defaultType": "future"}})


def _lock_age_minutes(path: Path) -> float:
    modified = pd.Timestamp.fromtimestamp(path.stat().st_mtime, tz="UTC")
    return (pd.Timestamp.now(tz="UTC") - modified).total_seconds() / 60.0


class PaperRunnerLock:
    """Simple single-instance lock for the paper runner."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or getattr(config, "PAPER_LOCK_FILE", "paper_runner.lock"))
        self.fd: int | None = None
        self.created_at: str | None = None

    def __enter__(self):
        stale_after = float(getattr(config, "PAPER_LOCK_STALE_MINUTES", 240))
        if self.path.exists():
            age = _lock_age_minutes(self.path)
            if age <= stale_after:
                raise RuntimeError(f"paper runner already locked by {self.path} age={age:.1f}m")
            self.path.unlink()

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        self.fd = os.open(str(self.path), flags)
        self.created_at = _utc_now()
        self.refresh()
        return self

    def refresh(self) -> None:
        if self.fd is None:
            raise RuntimeError("paper runner lock is not held")
        payload = {
            "pid": os.getpid(),
            "created_at": self.created_at or _utc_now(),
            "updated_at": _utc_now(),
        }
        os.lseek(self.fd, 0, os.SEEK_SET)
        os.ftruncate(self.fd, 0)
        os.write(self.fd, json.dumps(payload, sort_keys=True).encode("utf-8"))
        os.fsync(self.fd)

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _load_state(reset: bool = False) -> dict[str, Any]:
    path = Path(config.PAPER_STATE_FILE)
    if reset or not path.exists():
        return {
            "wallet": float(getattr(config, "PAPER_START_BALANCE", config.CAPITAL_USDT)),
            "positions": {},
            "created_at": _utc_now(),
            "run_tag": getattr(config, "PAPER_RUN_TAG", "default"),
            "timeframe": getattr(config, "TIMEFRAME", ""),
            "scaled_lookbacks": bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False)),
        }
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _utc_now()
    _atomic_write_json(config.PAPER_STATE_FILE, state)


def _append_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    file_path = Path(path)
    file_exists = file_path.exists()
    fieldnames: list[str] = []
    existing_rows: list[dict[str, Any]] = []
    existing_fieldnames: list[str] = []
    if file_exists:
        with file_path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fieldnames = reader.fieldnames or []
            fieldnames.extend(existing_fieldnames)
            existing_rows = list(reader)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not file_exists:
        mode = "w"
        output_rows = rows
        target_path = file_path
    elif any(key not in existing_fieldnames for row in rows for key in row):
        mode = "w"
        output_rows = existing_rows + rows
        target_path = file_path.with_name(f".{file_path.name}.{os.getpid()}.tmp")
    else:
        mode = "a"
        output_rows = rows
        target_path = file_path

    if file_path.parent and str(file_path.parent) != ".":
        file_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if mode == "w":
            writer.writeheader()
        writer.writerows(output_rows)
        _fsync_file(f)
    if target_path != file_path:
        os.replace(target_path, file_path)


def _append_error(error: Exception, attempt: int | None = None) -> None:
    _append_csv(getattr(config, "PAPER_ERRORS_CSV", "paper_errors.csv"), [{
        "run_at_utc": _utc_now(),
        "run_tag": getattr(config, "PAPER_RUN_TAG", "default"),
        "timeframe": getattr(config, "TIMEFRAME", ""),
        "pid": os.getpid(),
        "attempt": attempt if attempt is not None else "",
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exc(limit=5),
    }])


def _prepare_symbol(exchange: ccxt.Exchange, symbol: str) -> pd.DataFrame:
    saved = config.SYMBOL
    try:
        config.SYMBOL = symbol
        df = data.fetch_ohlcv(exchange)
        df_daily = data.fetch_daily_ohlcv(exchange, limit=200)
        df_weekly = data.fetch_weekly_ohlcv(exchange, limit=200)
        df = ind.add_indicators(df)
        df = ind.add_daily_trend(df, df_daily)
        df = ind.add_weekly_trend(df, df_weekly)
        if getattr(config, "FLOW_DATA_ENABLED", True):
            flow_result = flow_data.fetch_recent_flow(exchange, symbol)
            df = flow_data.add_flow_indicators(df, flow_result.data)
        return df
    finally:
        config.SYMBOL = saved


def _latest_price(df: pd.DataFrame) -> float:
    return float(df["close"].iloc[-2])


def _equity(wallet: float, positions: dict[str, dict[str, Any]], frames: dict[str, pd.DataFrame]) -> tuple[float, float]:
    unrealized = 0.0
    for sym, pos in positions.items():
        df = frames.get(sym)
        if df is None or df.empty:
            continue
        price = _latest_price(df)
        if pos["side"] == strat.LONG:
            unrealized += (price - pos["entry"]) * pos["size"]
        else:
            unrealized += (pos["entry"] - price) * pos["size"]
    return wallet + unrealized, unrealized


def _apply_slippage(price: float, side: str, opening: bool) -> float:
    rate = getattr(config, "PAPER_ENTRY_SLIPPAGE_RATE", 0.0) if opening else getattr(config, "PAPER_EXIT_SLIPPAGE_RATE", 0.0)
    if side == strat.LONG:
        return price * (1 + rate) if opening else price * (1 - rate)
    return price * (1 - rate) if opening else price * (1 + rate)


def _close_position(pos: dict[str, Any], exit_price: float, exit_ts, reason: str) -> tuple[float, dict[str, Any]]:
    side = pos["side"]
    slipped_exit = _apply_slippage(float(exit_price), side, opening=False)
    if side == strat.LONG:
        gross = (slipped_exit - pos["entry"]) * pos["size"]
    else:
        gross = (pos["entry"] - slipped_exit) * pos["size"]

    notional = (pos["entry"] + slipped_exit) / 2 * pos["size"]
    commission = abs(notional) * config.ROUND_TRIP_FEE_RATE
    slippage_cost = abs(notional) * config.SLIPPAGE_RATE_ROUND_TRIP
    pnl = gross - commission - slippage_cost
    entry_equity = float(pos.get("entry_equity") or 0.0)

    row = {
        "closed_at_utc": _utc_now(),
        "run_tag": getattr(config, "PAPER_RUN_TAG", "default"),
        "timeframe": getattr(config, "TIMEFRAME", ""),
        "symbol": pos["symbol"],
        "entry_time": pos["entry_time"],
        "exit_time": pd.Timestamp(exit_ts).isoformat(),
        "side": side,
        "entry": round(pos["entry"], 6),
        "exit": round(slipped_exit, 6),
        "size": round(pos["size"], 8),
        "notional": round(notional, 4),
        "commission": round(commission, 6),
        "slippage": round(slippage_cost, 6),
        "pnl": round(pnl, 6),
        "pnl_return_pct": round((pnl / entry_equity * 100.0) if entry_equity > 0 else 0.0, 6),
        "exit_reason": reason,
        "entry_signal": pos.get("entry_signal", pos.get("side", "")),
        "entry_regime": pos.get("entry_regime", ""),
        "entry_adx": pos.get("entry_adx", ""),
        "entry_rsi": pos.get("entry_rsi", ""),
        "entry_orderbook_reason": pos.get("entry_orderbook_reason", ""),
        "risk_reasons": pos.get("risk_reasons", ""),
        "max_favorable": round(float(pos.get("max_favorable") or 0.0), 6),
        "max_adverse": round(float(pos.get("max_adverse") or 0.0), 6),
        "max_favorable_pct": round(float(pos.get("max_favorable_pct") or 0.0), 6),
        "max_adverse_pct": round(float(pos.get("max_adverse_pct") or 0.0), 6),
    }
    return pnl, row


def _update_position_excursions(pos: dict[str, Any], bar: pd.Series) -> None:
    entry = float(pos["entry"])
    size = float(pos["size"])
    entry_equity = float(pos.get("entry_equity") or 0.0)
    if pos["side"] == strat.LONG:
        favorable = max(0.0, (float(bar["high"]) - entry) * size)
        adverse = max(0.0, (entry - float(bar["low"])) * size)
    else:
        favorable = max(0.0, (entry - float(bar["low"])) * size)
        adverse = max(0.0, (float(bar["high"]) - entry) * size)

    pos["max_favorable"] = max(float(pos.get("max_favorable") or 0.0), favorable)
    pos["max_adverse"] = max(float(pos.get("max_adverse") or 0.0), adverse)
    if entry_equity > 0:
        pos["max_favorable_pct"] = max(float(pos.get("max_favorable_pct") or 0.0), pos["max_favorable"] / entry_equity * 100.0)
        pos["max_adverse_pct"] = max(float(pos.get("max_adverse_pct") or 0.0), pos["max_adverse"] / entry_equity * 100.0)


def _closed_on_current_bar(closed_bars: dict[str, str], symbol: str, bar: pd.Series) -> bool:
    closed_at = closed_bars.get(symbol)
    if not closed_at:
        return False
    try:
        return eg._normalized_timestamp(closed_at) == eg._normalized_timestamp(bar.name)
    except Exception:
        return False


def _manage_positions(state: dict[str, Any], frames: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    trades: list[dict[str, Any]] = []
    closed_bars: dict[str, str] = {}
    positions = state["positions"]
    for sym in list(positions.keys()):
        df = frames.get(sym)
        if df is None or len(df) < 3:
            continue
        pos = positions[sym]
        bar = df.iloc[-2]
        window = df
        if eg.same_closed_bar_as_entry(pos, bar):
            continue
        _update_position_excursions(pos, bar)

        decision = eg.stop_decision(pos, bar)
        exit_reason = None
        exit_price = None
        if decision.hit:
            exit_reason = decision.reason
            exit_price = decision.price
        elif strat.check_exit(window, pos["side"]):
            exit_reason = "trend_exit"
            exit_price = float(bar["close"])

        if exit_reason and exit_price is not None:
            pnl, row = _close_position(pos, float(exit_price), bar.name, exit_reason)
            state["wallet"] = float(state["wallet"]) + pnl
            trades.append(row)
            closed_bars[sym] = pd.Timestamp(bar.name).isoformat()
            del positions[sym]
            continue

        if not eg.should_skip_trailing_update(bar).ok:
            continue
        if pos["side"] == strat.LONG:
            pos["extreme"] = max(float(pos["extreme"]), float(bar["high"]))
            new_sl = strat.trailing_stop(float(pos["entry"]), float(pos["extreme"]), pos["side"], float(pos.get("atr") or 0))
            if new_sl > float(pos["sl"]):
                pos["sl"] = new_sl
                pos["hard_sl"] = eg.hard_stop_from_soft(new_sl, float(pos.get("atr") or 0), pos["side"])
        else:
            pos["extreme"] = min(float(pos["extreme"]), float(bar["low"]))
            new_sl = strat.trailing_stop(float(pos["entry"]), float(pos["extreme"]), pos["side"], float(pos.get("atr") or 0))
            if new_sl < float(pos["sl"]):
                pos["sl"] = new_sl
                pos["hard_sl"] = eg.hard_stop_from_soft(new_sl, float(pos.get("atr") or 0), pos["side"])
    return trades, closed_bars


def _decision_row(
    symbol: str,
    df: pd.DataFrame,
    signal: str | None,
    action: str,
    risk_decision: r.RiskDecision | None,
    guard: eg.GuardDecision | None,
    effective_risk: float | None,
    size: float | None,
    notional: float | None,
    skipped_reason: str = "",
) -> dict[str, Any]:
    bar = df.iloc[-2]
    return {
        "run_at_utc": _utc_now(),
        "run_tag": getattr(config, "PAPER_RUN_TAG", "default"),
        "timeframe": getattr(config, "TIMEFRAME", ""),
        "scaled_lookbacks": bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False)),
        "symbol": symbol,
        "bar_time": pd.Timestamp(bar.name).isoformat(),
        "action": action,
        "signal": signal or "",
        "skipped_reason": skipped_reason,
        "close": float(bar["close"]),
        "atr": float(bar.get("atr", 0) or 0),
        "regime": bar.get("regime", ""),
        "adx": float(bar.get("adx", 0) or 0),
        "rsi": float(bar.get("rsi", 0) or 0),
        "daily_trend": bar.get("daily_trend", ""),
        "weekly_trend": bar.get("weekly_trend", ""),
        "pattern_bias": bar.get("pattern_bias", ""),
        "pattern_score_long": bar.get("pattern_score_long", ""),
        "pattern_score_short": bar.get("pattern_score_short", ""),
        "flow_taker_buy_ratio": bar.get("flow_taker_buy_ratio", ""),
        "flow_top_long_short_ratio": bar.get("flow_top_long_short_ratio", ""),
        "flow_oi_change": bar.get("flow_oi_change", ""),
        "flow_funding_rate": bar.get("flow_funding_rate", ""),
        "flow_fresh": bar.get("flow_fresh", ""),
        "flow_bucket_age_minutes": bar.get("flow_bucket_age_minutes", ""),
        "flow_snapshot_age_minutes": bar.get("flow_snapshot_age_minutes", ""),
        "risk_mult": risk_decision.multiplier if risk_decision else "",
        "risk_block": risk_decision.block_new_entries if risk_decision else "",
        "risk_reasons": "|".join(risk_decision.reasons) if risk_decision else "",
        "effective_risk_pct": round((effective_risk or 0.0) * 100.0, 6) if effective_risk is not None else "",
        "orderbook_ok": guard.ok if guard else "",
        "orderbook_reason": guard.reason if guard else "",
        "size": size if size is not None else "",
        "notional": round(notional, 4) if notional is not None else "",
    }


def run_once(reset: bool = False) -> dict[str, Any]:
    exchange = _public_exchange()
    state = _load_state(reset=reset)
    state["run_tag"] = getattr(config, "PAPER_RUN_TAG", "default")
    state["timeframe"] = getattr(config, "TIMEFRAME", "")
    state["scaled_lookbacks"] = bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False))
    state["symbols"] = list(getattr(config, "SYMBOLS", []))
    frames: dict[str, pd.DataFrame] = {}
    for symbol in config.SYMBOLS:
        frames[symbol] = _prepare_symbol(exchange, symbol)

    closed_trades, closed_bars = _manage_positions(state, frames)
    if closed_trades:
        _append_csv(config.PAPER_TRADES_CSV, closed_trades)

    wallet = float(state["wallet"])
    equity, unrealized = _equity(wallet, state["positions"], frames)
    decision_rows: list[dict[str, Any]] = []

    for symbol in config.SYMBOLS:
        df = frames[symbol]
        if symbol in state["positions"]:
            decision_rows.append(_decision_row(symbol, df, None, "hold", None, None, None, None, None))
            continue

        signal = strat.get_signal(df)
        if signal is None:
            decision_rows.append(_decision_row(symbol, df, None, "no_signal", None, None, None, None, None))
            continue

        if _closed_on_current_bar(closed_bars, symbol, df.iloc[-2]):
            decision_rows.append(_decision_row(symbol, df, signal, "skip", None, None, None, None, None, "same_bar_reentry_guard"))
            continue

        if len(state["positions"]) >= config.MAX_OPEN_POSITIONS:
            decision_rows.append(_decision_row(symbol, df, signal, "skip", None, None, None, None, None, "max_positions"))
            continue

        bar = df.iloc[-2]
        atr = float(bar["atr"])
        ref_price = float(bar["close"])
        base_risk = r.correlation_aware_risk(len(state["positions"]), config.RISK_PER_TRADE_PCT)
        risk_decision = r.entry_risk_decision(bar, signal, ts=bar.name)
        effective_risk = base_risk * risk_decision.multiplier
        if risk_decision.block_new_entries:
            decision_rows.append(_decision_row(symbol, df, signal, "skip", risk_decision, None, effective_risk, None, None, "risk_block"))
            continue

        size = round((equity * effective_risk) / (atr * config.SL_ATR_MULT), 6)
        entry = _apply_slippage(ref_price, signal, opening=True)
        notional = size * entry
        guard = eg.pre_trade_liquidity_check(exchange, symbol, signal, notional, ref_price)
        if not guard.ok:
            decision_rows.append(_decision_row(symbol, df, signal, "skip", risk_decision, guard, effective_risk, size, notional, "orderbook_guard"))
            continue
        if notional < MIN_NOTIONAL_USDT:
            decision_rows.append(_decision_row(symbol, df, signal, "skip", risk_decision, guard, effective_risk, size, notional, "min_notional"))
            continue

        sl, _ = r.sl_tp_prices(entry, atr, signal)
        hard_sl = eg.hard_stop_from_soft(sl, atr, signal)
        liq = liquidation.liquidation_guard_decision(entry, signal, hard_sl, leverage=config.LEVERAGE)
        if not liq.ok:
            decision_rows.append(_decision_row(symbol, df, signal, "skip", risk_decision, guard, effective_risk, size, notional, liq.reason))
            continue

        state["positions"][symbol] = {
            "symbol": symbol,
            "side": signal,
            "entry_signal": signal,
            "entry": entry,
            "size": size,
            "sl": sl,
            "hard_sl": hard_sl,
            "liquidation_price": liq.liquidation_price,
            "atr": atr,
            "extreme": entry,
            "entry_time": pd.Timestamp(bar.name).isoformat(),
            "entry_equity": equity,
            "entry_regime": bar.get("regime", ""),
            "entry_adx": float(bar.get("adx", 0) or 0),
            "entry_rsi": float(bar.get("rsi", 0) or 0),
            "entry_daily_trend": bar.get("daily_trend", ""),
            "entry_weekly_trend": bar.get("weekly_trend", ""),
            "entry_orderbook_reason": guard.reason,
            "risk_pct": effective_risk,
            "risk_mult": risk_decision.multiplier,
            "risk_reasons": "|".join(risk_decision.reasons),
            "notional": notional,
            "max_favorable": 0.0,
            "max_adverse": 0.0,
            "max_favorable_pct": 0.0,
            "max_adverse_pct": 0.0,
        }
        decision_rows.append(_decision_row(symbol, df, signal, "paper_open", risk_decision, guard, effective_risk, size, notional))

    wallet = float(state["wallet"])
    equity, unrealized = _equity(wallet, state["positions"], frames)
    _append_csv(config.PAPER_DECISIONS_CSV, decision_rows)
    _append_csv(config.PAPER_EQUITY_CSV, [{
        "run_at_utc": _utc_now(),
        "run_tag": getattr(config, "PAPER_RUN_TAG", "default"),
        "timeframe": getattr(config, "TIMEFRAME", ""),
        "scaled_lookbacks": bool(getattr(config, "PAPER_SCALED_LOOKBACKS", False)),
        "wallet": round(wallet, 6),
        "equity": round(equity, 6),
        "unrealized": round(unrealized, 6),
        "open_positions": len(state["positions"]),
    }])
    _save_state(state)
    _write_heartbeat(
        "ok",
        wallet=round(wallet, 6),
        equity=round(equity, 6),
        unrealized=round(unrealized, 6),
        open_positions=len(state["positions"]),
        decisions=len(decision_rows),
        closed_trades=len(closed_trades),
    )
    return {
        "wallet": wallet,
        "equity": equity,
        "unrealized": unrealized,
        "open_positions": len(state["positions"]),
        "decisions": decision_rows,
        "closed_trades": closed_trades,
    }


def _run_once_with_retry(reset: bool = False) -> dict[str, Any]:
    max_retries = int(getattr(config, "PAPER_MAX_RETRIES", 3))
    base_sleep = float(getattr(config, "PAPER_RETRY_BASE_SECONDS", 5))
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return run_once(reset=reset)
        except Exception as exc:
            last_error = exc
            _append_error(exc, attempt=attempt)
            _write_heartbeat("error", attempt=attempt, error_type=type(exc).__name__, error=str(exc))
            if attempt < max_retries:
                time.sleep(base_sleep * attempt)
    assert last_error is not None
    raise last_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one telemetry cycle.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument("--interval-minutes", type=float, default=60.0)
    parser.add_argument("--reset", action="store_true", help="Reset paper state before the first run.")
    parser.add_argument("--tag", default="", help="Isolate runtime files with a run tag, e.g. shadow_2h.")
    parser.add_argument("--timeframe", default="", help="Temporarily override config.TIMEFRAME for this runner.")
    parser.add_argument(
        "--scale-lookbacks",
        action="store_true",
        help="Scale indicator lookbacks so the run keeps roughly the current 4h calendar horizon.",
    )
    args = parser.parse_args()

    if not args.once and not args.loop:
        args.once = True

    with paper_runtime.temporary_paper_runtime(
        tag=args.tag,
        timeframe=args.timeframe or None,
        scale_lookbacks=args.scale_lookbacks,
    ), PaperRunnerLock() as lock:
        first = True
        while True:
            try:
                result = _run_once_with_retry(reset=args.reset and first)
                lock.refresh()
                print(
                    "paper telemetry:",
                    f"tag={getattr(config, 'PAPER_RUN_TAG', 'default')}",
                    f"timeframe={getattr(config, 'TIMEFRAME', '')}",
                    f"equity={result['equity']:.2f}",
                    f"wallet={result['wallet']:.2f}",
                    f"open={result['open_positions']}",
                    f"decisions={len(result['decisions'])}",
                    f"closed={len(result['closed_trades'])}",
                    flush=True,
                )
            except Exception as exc:
                if args.once:
                    raise
                sleep_seconds = float(getattr(config, "PAPER_ERROR_SLEEP_SECONDS", 300))
                print(f"paper telemetry error: {type(exc).__name__}: {exc}; sleeping {sleep_seconds:.0f}s", flush=True)
                lock.refresh()
                time.sleep(sleep_seconds)
                first = False
                continue

            if args.once:
                break
            first = False
            lock.refresh()
            time.sleep(max(args.interval_minutes, 1.0) * 60)


if __name__ == "__main__":
    main()
