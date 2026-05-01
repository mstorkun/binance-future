"""
Gerçek portföy backtest — tek sermaye, çoklu sembol, eşzamanlı pozisyonlar.

Önceki `multi_symbol_backtest.py` her sembolü ayrı koşturup PnL'leri topluyor;
bu, sermaye paylaşımı ve eşzamanlı pozisyon kilitlemesini modellemez.

Bu motor:
- Tek sermaye havuzu (CAPITAL_USDT)
- MAX_OPEN_POSITIONS global limit
- Pozisyon margin kullanımı sermayeden düşülür (yeni trade için yetersizse pas)
- Bar-bazlı ortak zaman çizelgesi
"""
from __future__ import annotations

import pandas as pd
import ccxt
import config
import execution_guard as eg
import flow_data
import indicators as ind
import liquidation
import exit_ladder
import pair_universe
import protections
import strategy as strat
import risk as r
from backtest import _fetch_paginated, fetch_funding_history, _funding_cost


def _prepare_symbol_df(
    symbol: str,
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    df_1w: pd.DataFrame | None = None,
    flow_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Sembol için tüm indikatörleri ekle, daily trend merge et."""
    df = ind.add_indicators(df_4h)
    if df_1d is not None and not df_1d.empty:
        df = ind.add_daily_trend(df, df_1d)
    if df_1w is not None and not df_1w.empty:
        df = ind.add_weekly_trend(df, df_1w)
    if flow_df is not None and not flow_df.empty:
        df = flow_data.add_flow_indicators(df, flow_df)
    return df


def run_portfolio_backtest(
    symbols: list[str],
    data_by_symbol: dict[str, dict],
    start_balance: float,
    max_concurrent: int = 2,
    risk_per_trade: float | None = None,
    leverage: float | None = None,
    risk_basis: str | None = None,
    enable_circuit_breaker: bool = True,
    enable_corr_sizing: bool = True,
    enable_protections: bool | None = None,
    enable_exit_ladder: bool | None = None,
    enable_pair_universe: bool | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (trades_df, equity_df).
    Eşzamanlı timeline: tüm sembollerin 4H bar'ları birleştirilip kronolojik dolaşılır.
    """
    if risk_per_trade is None:
        risk_per_trade = config.RISK_PER_TRADE_PCT
    if leverage is None:
        leverage = config.LEVERAGE
    if risk_basis is None:
        risk_basis = getattr(config, "RISK_BASIS", "portfolio")
    if enable_protections is None:
        enable_protections = getattr(config, "PROTECTIONS_ENABLED", False)
    if enable_exit_ladder is None:
        enable_exit_ladder = getattr(config, "EXIT_LADDER_ENABLED", False)
    if enable_pair_universe is None:
        enable_pair_universe = getattr(config, "PAIR_UNIVERSE_ENABLED", False)
    if enable_pair_universe:
        symbols = pair_universe.select_symbols(symbols, data_by_symbol)

    # Ortak timeline
    all_timestamps = set()
    for sym in symbols:
        all_timestamps.update(data_by_symbol[sym]["df"].index)
    timeline = sorted(all_timestamps)
    allocation_count = max(len(symbols), 1)

    wallet = float(start_balance)
    open_positions: dict[str, dict] = {}
    trades = []
    equity_history = []

    # Circuit breaker durumu
    peak_equity        = float(start_balance)
    cb_paused_until    = None   # ts; bu zamana kadar yeni trade yok
    cb_risk_multiplier = 1.0    # -10% DD'de 0.5'e düşer
    cb_locked          = False  # -30% DD'de manuel onay gerekli

    for ts in timeline:
        # Futures equity: wallet balance plus open-position unrealized PnL.
        equity, unrealized, used_margin = _account_state(
            wallet, open_positions, data_by_symbol, ts
        )

        # 1) Açık pozisyonları kontrol et: SL hit, trailing güncelle, trend exit
        for sym in list(open_positions.keys()):
            df = data_by_symbol[sym]["df"]
            if ts not in df.index:
                continue
            pos = open_positions[sym]
            bar = df.loc[ts]
            window = df.loc[:ts]

            stop_decision = eg.stop_decision(pos, bar)
            exit_price = stop_decision.price

            # Trend exit?
            trend_exit = strat.check_exit(window, pos["side"]) if not stop_decision.hit else False
            exit_reason = None
            if stop_decision.hit:
                exit_reason = stop_decision.reason
            elif trend_exit:
                exit_reason = "trend_exit"
                exit_price = bar["close"]    # bar kapanış

            if exit_reason:
                pnl = _close_position(pos, sym, exit_price, ts, data_by_symbol, trades, ts, exit_reason)
                wallet += pnl
                del open_positions[sym]
                continue

            if enable_exit_ladder:
                pnl = _process_exit_ladder(pos, sym, bar, ts, data_by_symbol, trades)
                wallet += pnl
                if pos.get("size", 0.0) <= 0:
                    del open_positions[sym]
                    continue

            # Trailing güncelle
            trailing_guard = eg.should_skip_trailing_update(bar)
            if trailing_guard.ok:
                if pos["side"] == strat.LONG:
                    pos["extreme"] = max(pos["extreme"], bar["high"])
                else:
                    pos["extreme"] = min(pos["extreme"], bar["low"])
                new_sl = strat.trailing_stop(pos["entry"], pos["extreme"], pos["side"], pos.get("atr"))
                if pos["side"] == strat.LONG and new_sl > pos["sl"]:
                    pos["sl"] = new_sl
                    pos["hard_sl"] = eg.hard_stop_from_soft(new_sl, pos["atr"], pos["side"])
                elif pos["side"] == strat.SHORT and new_sl < pos["sl"]:
                    pos["sl"] = new_sl
                    pos["hard_sl"] = eg.hard_stop_from_soft(new_sl, pos["atr"], pos["side"])

        # Circuit breaker: equity peak'e göre drawdown
        equity, unrealized, used_margin = _account_state(
            wallet, open_positions, data_by_symbol, ts
        )

        peak_equity = max(peak_equity, equity)
        if enable_circuit_breaker:
            dd_pct = (peak_equity - equity) / peak_equity
            if dd_pct >= 0.30 and not cb_locked:
                cb_locked = True
            if dd_pct >= 0.20:
                cb_paused_until = ts + pd.Timedelta(days=7)
                cb_risk_multiplier = 0.5
            elif dd_pct >= 0.10:
                cb_risk_multiplier = 0.5
            else:
                cb_risk_multiplier = 1.0

        cb_blocking = cb_locked or (cb_paused_until is not None and ts < cb_paused_until)

        # 2) Yeni sinyaller (sadece kapasite varsa ve CB açık değilse)
        if not cb_blocking and len(open_positions) < max_concurrent:
            for sym in symbols:
                if sym in open_positions:
                    continue
                if len(open_positions) >= max_concurrent:
                    break
                df = data_by_symbol[sym]["df"]
                if ts not in df.index:
                    continue
                window = df.loc[:ts]
                if len(window) < 3:
                    continue
                signal = strat.get_signal(window)
                if signal is None:
                    continue

                bar = df.loc[ts]
                # Bir sonraki bar'ın open'ı ile gir (slippage/realism)
                idx_pos = df.index.get_loc(ts)
                if idx_pos + 1 >= len(df):
                    continue
                next_bar = df.iloc[idx_pos + 1]
                entry = next_bar["open"]
                atr   = bar["atr"]

                # Pozisyon boyutu — corr-aware + circuit breaker risk multiplier
                effective_risk = risk_per_trade
                if enable_corr_sizing:
                    effective_risk = r.correlation_aware_risk(len(open_positions), risk_per_trade)
                if enable_circuit_breaker:
                    effective_risk *= cb_risk_multiplier
                risk_decision = r.entry_risk_decision(bar, signal, ts=ts)
                if risk_decision.block_new_entries:
                    continue
                if enable_protections:
                    protection = protections.protection_decision(
                        sym,
                        ts,
                        trades,
                        equity=equity,
                        peak_equity=peak_equity,
                    )
                    if protection.block_new_entries:
                        continue
                effective_risk *= risk_decision.multiplier

                if risk_basis == "portfolio":
                    allocated = equity
                else:
                    allocated = equity / allocation_count
                size = (allocated * effective_risk) / (atr * config.SL_ATR_MULT)
                size = round(size, 6)

                notional = size * entry
                if notional < 100:    # min notional
                    continue
                margin = notional / leverage
                available_margin = max(wallet - used_margin, 0.0)
                if margin > available_margin:
                    continue

                sl, _ = r.sl_tp_prices(entry, atr, signal)
                hard_sl = eg.hard_stop_from_soft(sl, atr, signal)
                liq_guard = liquidation.liquidation_guard_decision(entry, signal, hard_sl, leverage=leverage)
                if not liq_guard.ok:
                    continue
                open_positions[sym] = {
                    "side": signal, "entry": entry, "size": size,
                    "sl": sl, "hard_sl": hard_sl, "extreme": entry,
                    "entry_time": next_bar.name, "atr": atr,
                    "margin": margin, "notional": notional,
                    "entry_equity": equity,
                    "liquidation_price": liq_guard.liquidation_price,
                    "risk_pct": effective_risk,
                    "risk_mult": risk_decision.multiplier,
                    "risk_reasons": "|".join(risk_decision.reasons),
                    "exit_plan": exit_ladder.build_exit_plan(entry, atr, signal, enabled=enable_exit_ladder),
                    "exit_steps_filled": 0,
                    "initial_size": size,
                }
                used_margin += margin

        equity, unrealized, used_margin = _account_state(
            wallet, open_positions, data_by_symbol, ts
        )
        equity_history.append({
            "timestamp": ts,
            "equity": equity,
            "wallet": wallet,
            "unrealized": unrealized,
            "used_margin": used_margin,
            "available_margin": max(wallet - used_margin, 0.0),
            "open_positions": len(open_positions),
        })

    return pd.DataFrame(trades), pd.DataFrame(equity_history)


def _account_state(wallet: float, open_positions: dict, data_by_symbol: dict, ts) -> tuple[float, float, float]:
    unrealized = 0.0
    used_margin = 0.0
    for sym, pos in open_positions.items():
        used_margin += pos["margin"]
        df = data_by_symbol[sym]["df"]
        if ts not in df.index:
            continue
        cur_price = df.loc[ts, "close"]
        if pos["side"] == strat.LONG:
            unrealized += (cur_price - pos["entry"]) * pos["size"]
        else:
            unrealized += (pos["entry"] - cur_price) * pos["size"]
    return wallet + unrealized, unrealized, used_margin


def _gross_pnl(pos: dict, exit_price: float) -> float:
    if pos["side"] == strat.LONG:
        return (exit_price - pos["entry"]) * pos["size"]
    return (pos["entry"] - exit_price) * pos["size"]


def _process_exit_ladder(pos: dict, sym: str, bar, ts, data_by_symbol, trades) -> float:
    plan = pos.get("exit_plan") or []
    total_pnl = 0.0
    while int(pos.get("exit_steps_filled", 0)) < len(plan) and float(pos.get("size", 0.0)) > 0:
        step = plan[int(pos.get("exit_steps_filled", 0))]
        hit = (
            pos["side"] == strat.LONG and float(bar["high"]) >= step.target
        ) or (
            pos["side"] == strat.SHORT and float(bar["low"]) <= step.target
        )
        if not hit:
            break

        close_size = min(float(pos["size"]), float(pos.get("initial_size", pos["size"])) * step.close_fraction)
        pnl = _close_position(
            pos,
            sym,
            step.target,
            ts,
            data_by_symbol,
            trades,
            ts,
            f"{step.name}_partial",
            size_override=close_size,
        )
        total_pnl += pnl
        old_size = float(pos["size"])
        pos["size"] = round(max(0.0, old_size - close_size), 8)
        if old_size > 0:
            remaining_ratio = pos["size"] / old_size
            pos["margin"] = float(pos.get("margin", 0.0)) * remaining_ratio
            pos["notional"] = float(pos.get("notional", 0.0)) * remaining_ratio

        pos["exit_steps_filled"] = int(pos.get("exit_steps_filled", 0)) + 1
        new_stop = exit_ladder.stop_after_filled_steps(pos["entry"], pos["side"], plan, int(pos["exit_steps_filled"]))
        if new_stop is not None:
            pos["sl"] = new_stop
            pos["hard_sl"] = eg.hard_stop_from_soft(new_stop, pos["atr"], pos["side"])
    return total_pnl


def _close_position(
    pos: dict,
    sym: str,
    exit_price: float,
    exit_ts,
    data_by_symbol,
    trades,
    ts,
    exit_reason: str,
    size_override: float | None = None,
):
    close_size = float(pos["size"] if size_override is None else size_override)
    close_pos = dict(pos)
    close_pos["size"] = close_size
    notional = (pos["entry"] + exit_price) / 2 * close_size
    commission = notional * config.ROUND_TRIP_FEE_RATE
    slippage   = notional * config.SLIPPAGE_RATE_ROUND_TRIP
    funding_rates = data_by_symbol[sym].get("funding")
    bars_held = max(1, _bars_between(data_by_symbol[sym]["df"], pos["entry_time"], exit_ts))
    funding = _funding_cost(
        funding_rates=funding_rates,
        entry_time=pos["entry_time"],
        exit_time=exit_ts,
        notional=abs(notional),
        side=pos["side"],
        fallback_periods=bars_held / 2.0,
    )
    gross = _gross_pnl(close_pos, exit_price)
    pnl = gross - commission - slippage - funding
    entry_equity = float(pos.get("entry_equity") or 0.0)
    pnl_return_pct = (pnl / entry_equity * 100.0) if entry_equity > 0 else 0.0
    trades.append({
        "symbol":      sym,
        "entry_time":  pos["entry_time"],
        "exit_time":   exit_ts,
        "side":        pos["side"],
        "entry":       round(pos["entry"], 2),
        "exit":        round(exit_price, 2),
        "size":        round(pos["size"], 6),
        "notional":    round(notional, 2),
        "commission":  round(commission, 4),
        "slippage":    round(slippage, 4),
        "funding":     round(funding, 4),
        "bars_held":   bars_held,
        "exit_reason":  exit_reason,
        "soft_sl":      round(pos.get("sl", 0.0), 4),
        "hard_sl":      round(pos.get("hard_sl", 0.0), 4),
        "liquidation_price": round(pos["liquidation_price"], 4) if pos.get("liquidation_price") else None,
        "entry_equity": round(entry_equity, 4) if entry_equity else None,
        "pnl_return_pct": round(pnl_return_pct, 6),
        "risk_pct":    round(pos.get("risk_pct", 0.0), 5),
        "risk_mult":   round(pos.get("risk_mult", 1.0), 3),
        "risk_reasons": pos.get("risk_reasons", ""),
        "pnl":         round(pnl, 2),
    })
    return pnl


def _bars_between(df: pd.DataFrame, start_ts, end_ts) -> int:
    try:
        return df.index.get_loc(end_ts) - df.index.get_loc(start_ts)
    except Exception:
        return 1


def fetch_all_data(symbols: list[str], years: int = 3) -> dict:
    saved = config.SYMBOL
    out = {}
    flow_exchange = ccxt.binance({"options": {"defaultType": "future"}}) if getattr(config, "FLOW_BACKTEST_ENABLED", False) else None
    try:
        for sym in symbols:
            config.SYMBOL = sym
            df_4h    = _fetch_paginated(config.TIMEFRAME, years)
            df_1d    = _fetch_paginated(config.DAILY_TIMEFRAME, years)
            df_1w    = _fetch_paginated(config.WEEKLY_TIMEFRAME, years)
            funding  = fetch_funding_history(years)
            flow_df = None
            if flow_exchange is not None:
                flow_result = flow_data.fetch_recent_flow(flow_exchange, sym)
                if flow_result.warnings:
                    print(f"  {sym}: flow partial ({'; '.join(flow_result.warnings[:2])})")
                flow_df = flow_result.data
            df_with  = _prepare_symbol_df(sym, df_4h, df_1d, df_1w, flow_df)
            out[sym] = {"df": df_with, "funding": funding}
            print(f"  {sym}: {len(df_with)} bar (with indicators), funding {len(funding)}")
    finally:
        config.SYMBOL = saved
    return out


if __name__ == "__main__":
    SYMBOLS = list(config.SYMBOLS)
    print("Veri yukleniyor...")
    data = fetch_all_data(SYMBOLS, years=3)

    trades, equity = run_portfolio_backtest(
        SYMBOLS, data,
        start_balance=config.CAPITAL_USDT,
        max_concurrent=config.MAX_OPEN_POSITIONS,
    )

    if trades.empty:
        print("Trade yok.")
        exit(0)

    total_pnl   = trades["pnl"].sum()
    win_rate    = (trades["pnl"] > 0).sum() / len(trades) * 100
    final_eq    = equity["equity"].iloc[-1]
    peak        = equity["equity"].cummax()
    dd_series   = peak - equity["equity"]
    max_dd      = dd_series.max()
    max_dd_peak_pct = ((peak - equity["equity"]) / peak).max() * 100
    pct_return  = (final_eq - config.CAPITAL_USDT) / config.CAPITAL_USDT * 100
    cagr        = ((final_eq / config.CAPITAL_USDT) ** (1/3) - 1) * 100

    print(f"\n=== PORTFOY BACKTEST (gercek esansli) ===")
    print(f"Sembol sayisi    : {len(SYMBOLS)}")
    print(f"Toplam trade     : {len(trades)}")
    print(f"Win rate         : {win_rate:.1f}%")
    print(f"Baslangic        : {config.CAPITAL_USDT:.2f} USDT")
    print(f"Son equity       : {final_eq:.2f} USDT")
    print(f"Toplam getiri    : {pct_return:+.2f}% / 3 yil")
    print(f"CAGR             : {cagr:+.2f}%/yil")
    print(f"Max drawdown     : {max_dd:.2f} USDT ({max_dd/config.CAPITAL_USDT*100:.1f}% start, {max_dd_peak_pct:.1f}% peak)")
    print(f"Toplam komisyon  : {trades['commission'].sum():.2f}")
    print(f"Toplam slippage  : {trades['slippage'].sum():.2f}")
    print(f"Toplam funding   : {trades['funding'].sum():+.2f}")

    trades.to_csv("portfolio_trades.csv", index=False)
    equity.to_csv("portfolio_equity.csv", index=False)
    print(f"\nDetaylar: portfolio_trades.csv, portfolio_equity.csv")
