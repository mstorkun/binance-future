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
import time
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
import risk as r
import strategy as strat


MIN_NOTIONAL_USDT = 100.0


def _utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _public_exchange() -> ccxt.Exchange:
    return ccxt.binance({"options": {"defaultType": "future"}})


def _load_state(reset: bool = False) -> dict[str, Any]:
    path = Path(config.PAPER_STATE_FILE)
    if reset or not path.exists():
        return {
            "wallet": float(getattr(config, "PAPER_START_BALANCE", config.CAPITAL_USDT)),
            "positions": {},
            "created_at": _utc_now(),
        }
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = _utc_now()
    Path(config.PAPER_STATE_FILE).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _append_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    file_path = Path(path)
    file_exists = file_path.exists()
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with file_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


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
        "risk_reasons": pos.get("risk_reasons", ""),
    }
    return pnl, row


def _manage_positions(state: dict[str, Any], frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    trades: list[dict[str, Any]] = []
    positions = state["positions"]
    for sym in list(positions.keys()):
        df = frames.get(sym)
        if df is None or len(df) < 3:
            continue
        pos = positions[sym]
        bar = df.iloc[-2]
        window = df

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
    return trades


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
    frames: dict[str, pd.DataFrame] = {}
    for symbol in config.SYMBOLS:
        frames[symbol] = _prepare_symbol(exchange, symbol)

    closed_trades = _manage_positions(state, frames)
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
            "entry": entry,
            "size": size,
            "sl": sl,
            "hard_sl": hard_sl,
            "liquidation_price": liq.liquidation_price,
            "atr": atr,
            "extreme": entry,
            "entry_time": pd.Timestamp(bar.name).isoformat(),
            "entry_equity": equity,
            "risk_pct": effective_risk,
            "risk_mult": risk_decision.multiplier,
            "risk_reasons": "|".join(risk_decision.reasons),
            "notional": notional,
        }
        decision_rows.append(_decision_row(symbol, df, signal, "paper_open", risk_decision, guard, effective_risk, size, notional))

    wallet = float(state["wallet"])
    equity, unrealized = _equity(wallet, state["positions"], frames)
    _append_csv(config.PAPER_DECISIONS_CSV, decision_rows)
    _append_csv(config.PAPER_EQUITY_CSV, [{
        "run_at_utc": _utc_now(),
        "wallet": round(wallet, 6),
        "equity": round(equity, 6),
        "unrealized": round(unrealized, 6),
        "open_positions": len(state["positions"]),
    }])
    _save_state(state)
    return {
        "wallet": wallet,
        "equity": equity,
        "unrealized": unrealized,
        "open_positions": len(state["positions"]),
        "decisions": decision_rows,
        "closed_trades": closed_trades,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one telemetry cycle.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument("--interval-minutes", type=float, default=60.0)
    parser.add_argument("--reset", action="store_true", help="Reset paper state before the first run.")
    args = parser.parse_args()

    if not args.once and not args.loop:
        args.once = True

    first = True
    while True:
        result = run_once(reset=args.reset and first)
        print(
            "paper telemetry:",
            f"equity={result['equity']:.2f}",
            f"wallet={result['wallet']:.2f}",
            f"open={result['open_positions']}",
            f"decisions={len(result['decisions'])}",
            f"closed={len(result['closed_trades'])}",
        )
        if args.once:
            break
        first = False
        time.sleep(max(args.interval_minutes, 1.0) * 60)


if __name__ == "__main__":
    main()
