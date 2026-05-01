"""
Canlı bot ana döngüsü (Çoklu Sembol Portföy Modu).

Mimari sözleşme:
    data           : exchange + ohlcv + bakiye + pozisyon sorgusu
    indicators     : EMA / ADX / RSI / ATR (Wilder)
    strategy       : get_signal, check_exit, trailing_stop
    risk           : pozisyon boyutu, SL/TP fiyatları, günlük kayıp limiti
    order_manager  : atomik pozisyon açma, trailing SL update, market kapama

Akış:
  1. Bakiye + günlük kayıp kontrolü
  2. config.SYMBOLS içindeki her bir sembol için döngüye gir:
     a. config.SYMBOL değişkenini çalışma zamanında ez (diğer modüllerin çalışması için)
     b. OHLCV + indikatör hesabı
     c. Açık pozisyon var mı kontrol et
     d. Varsa check_exit (trend dönüşü) veya trailing SL update
     e. Yoksa get_signal → varsa open_position (atomik, bütçe/3 kullanılarak)
"""

import time
import logging
import schedule

import config
import data
import decision_snapshots
import flow_data
import indicators as ind
import strategy as strat
import risk as r
import execution_guard as eg
import live_state
import order_manager as om
import liquidation


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# Bot durumu (borsa durumu otorite — bunu cache olarak kullan)
exchange         = data.make_exchange()
daily_start_bal  = None
daily_stop_active = False
active_positions = live_state.load_positions()    # symbol -> {"side", "entry", "sl", "size", "extreme"}


def _persist_positions() -> None:
    try:
        live_state.save_positions(active_positions)
    except Exception as e:
        log.error(f"Live state yazilamadi: {e}")


def _has_open_position() -> dict | None:
    """Sembolde gerçek açık pozisyon var mı? Borsa state'i otorite."""
    try:
        if daily_stop_active:
            log.warning("Gunluk stop aktif; yeni islem acilmiyor. Reset 00:01'de yapilacak.")
            return

        positions = data.fetch_open_positions(exchange)
        return positions[0] if positions else None
    except Exception as e:
        log.error(f"Pozisyon sorgu hatası: {e}")
        return None


def _recover_position(live_pos: dict, df) -> dict:
    """
    Bot restart sonrası borsadaki pozisyondan state yeniden inşa et.
    SL fiyatı borsadan çekilir (fetch_open_orders), bulunamazsa ATR ile tahmin edilir.
    """
    contracts = float(live_pos.get("contracts") or 0)
    side      = live_pos.get("side") or (strat.LONG if contracts > 0 else strat.SHORT)
    entry     = float(live_pos.get("entryPrice") or df["close"].iloc[-1])

    atr = float(df["atr"].iloc[-2])
    real_sl, sl_order_id = om.fetch_active_sl(exchange)
    if real_sl is not None:
        hard_sl = real_sl
        extra = atr * getattr(config, "HARD_STOP_EXTRA_ATR", 1.0)
        sl = hard_sl + extra if side == strat.LONG else hard_sl - extra
        log.info(f"State recovery: borsadaki hard SL bulundu = {hard_sl:.2f} | soft SL~{sl:.2f}")
    else:
        sl, _ = r.sl_tp_prices(entry, atr, side)
        hard_sl = eg.hard_stop_from_soft(sl, atr, side)
        sl_order_id = None
        log.warning(f"State recovery: borsada SL bulunamadi, soft/hard tahmin = {sl:.2f}/{hard_sl:.2f}")
    liq_price = liquidation.approximate_liquidation_price(entry, side, leverage=config.LEVERAGE)

    log.info(f"State recovery: {side.upper()} entry={entry:.2f} size={abs(contracts)}")
    return {
        "side":         side,
        "entry":        entry,
        "sl":           sl,
        "hard_sl":      hard_sl,
        "liquidation_price": liq_price,
        "atr":          atr,
        "size":         abs(contracts),
        "extreme":      entry,
        "sl_order_id":  sl_order_id,
    }


def run():
    global daily_start_bal, daily_stop_active, active_positions
    log.info("--- Döngü başladı ---")

    try:
        # 1. Equity (free + margin + unrealized) — daily loss için doğru metrik
        equity  = data.fetch_equity(exchange)
        balance = data.fetch_balance(exchange)
        log.info(f"Equity: {equity:.2f} USDT | Free: {balance:.2f} USDT")

        if daily_start_bal is None:
            daily_start_bal = equity

        if r.daily_loss_exceeded(daily_start_bal, equity):
            log.warning("Günlük kayıp limiti! Tüm pozisyonlar kapatılıyor, bot duruyor.")
            for sym in config.SYMBOLS:
                config.SYMBOL = sym
                om.close_all(exchange)
            active_positions.clear()
            _persist_positions()
            daily_stop_active = True
            return

        # Global açık pozisyon sayısı (tüm semboller arası)
        try:
            all_open = data.fetch_all_open_positions(exchange, config.SYMBOLS)
            active_positions, removed_symbols = live_state.reconcile_positions(
                active_positions,
                all_open,
                config.SYMBOLS,
            )
            if removed_symbols:
                log.info(f"State reconciliation: lokal kapali pozisyonlar temizlendi: {removed_symbols}")
                _persist_positions()
            global_open_count = len(all_open)
        except Exception as e:
            log.warning(f"Global pozisyon sorgu hatası: {e}, lokal state kullanılıyor.")
            global_open_count = len(active_positions)
        log.info(f"Açık pozisyon: {global_open_count}/{config.MAX_OPEN_POSITIONS}")

        # Risk base: full portfolio equity or per-symbol sleeve.
        num_symbols = len(config.SYMBOLS)
        risk_base_balance = equity if config.RISK_BASIS == "portfolio" else equity / num_symbols

        for sym in config.SYMBOLS:
            config.SYMBOL = sym  # Global değişkeni o anki sembole ayarla
            log.info(f"--- Sembol inceleniyor: {sym} ---")
            
            try:
                # 2. Veri + indikatörler (4H + 1D)
                df    = data.fetch_ohlcv(exchange)
                df_1d = data.fetch_daily_ohlcv(exchange, limit=200)
                df_1w = data.fetch_weekly_ohlcv(exchange, limit=200)
                df    = ind.add_indicators(df)
                df    = ind.add_daily_trend(df, df_1d)
                df    = ind.add_weekly_trend(df, df_1w)
                if getattr(config, "FLOW_DATA_ENABLED", True):
                    flow_result = data.fetch_recent_flow(exchange)
                    flow_data.warn_once_for_flow(flow_result, sym)
                    df = flow_data.add_flow_indicators(df, flow_result.data)
                if len(df) < 3:
                    log.warning(f"[{sym}] Yeterli mum yok.")
                    continue
                bar_age = eg.closed_bar_age_decision(df, config.TIMEFRAME)
                if not bar_age.ok:
                    log.warning(
                        f"[{sym}] Kapali mum taze degil, sembol atlandi: "
                        f"{bar_age.reason} age={bar_age.age_minutes:.1f}m "
                        f"max={bar_age.max_age_minutes:.1f}m close={bar_age.bar_close_time}"
                    )
                    continue

                # 3. Borsa pozisyon state'i
                live_pos = _has_open_position()

                # 4a. Açık pozisyon var
                if live_pos:
                    if sym not in active_positions:
                        active_positions[sym] = _recover_position(live_pos, df)
                        _persist_positions()

                    pos = active_positions[sym]
                    closed_bar = df.iloc[-2]
                    cur_price = float(closed_bar["close"])

                    stop_decision = eg.stop_decision(pos, closed_bar)
                    if stop_decision.hit:
                        log.info(
                            f"[{sym}] {stop_decision.reason} teyit edildi -> "
                            f"{pos['side'].upper()} kapatiliyor."
                        )
                        om.close_position_market(exchange, pos["side"], pos["size"])
                        active_positions.pop(sym, None)
                        _persist_positions()
                        continue

                    # Trend tersine döndü mü?
                    if strat.check_exit(df, pos["side"]):
                        log.info(f"[{sym}] Trend tersine döndü → {pos['side'].upper()} kapatılıyor.")
                        om.close_position_market(exchange, pos["side"], pos["size"])
                        active_positions.pop(sym, None)
                        _persist_positions()
                        continue

                    # Extreme güncelle
                    if pos["side"] == strat.LONG:
                        pos["extreme"] = max(pos["extreme"], float(closed_bar["high"]))
                    else:
                        pos["extreme"] = min(pos["extreme"], float(closed_bar["low"]))
                    _persist_positions()

                    # Trailing SL hesapla ve gerekirse borsada güncelle
                    om.update_trailing_sl(exchange, pos, cur_price, pos["extreme"], bar=closed_bar)
                    _persist_positions()
                    continue

                # 4b. Açık pozisyon yok — bot state'i temizle, yeni sinyal ara
                if sym in active_positions:
                    log.info(f"[{sym}] Pozisyon dışarıda kapanmış (SL veya manuel).")
                    active_positions.pop(sym, None)
                    _persist_positions()

                signal = strat.get_signal(df)
                log.info(f"[{sym}] Sinyal: {signal or 'YOK'}")
                if signal is None:
                    continue

                # MAX_OPEN_POSITIONS guard (tüm semboller arası global limit)
                if global_open_count >= config.MAX_OPEN_POSITIONS:
                    log.info(f"[{sym}] Max pozisyon limiti ({config.MAX_OPEN_POSITIONS}) dolu, sinyal atlandı.")
                    continue

                # 5. Yeni pozisyon aç
                price = float(df["close"].iloc[-2])   # son kapanan bar
                atr   = float(df["atr"].iloc[-2])
                signal_bar = df.iloc[-2]
                risk_decision = r.entry_risk_decision(signal_bar, signal, ts=signal_bar.name)
                base_risk = r.correlation_aware_risk(global_open_count, config.RISK_PER_TRADE_PCT)
                effective_risk = base_risk * risk_decision.multiplier
                decision_snapshot = decision_snapshots.build_entry_snapshot(
                    symbol=sym,
                    timeframe=config.TIMEFRAME,
                    signal=signal,
                    bar=signal_bar,
                    equity=equity,
                    free_balance=balance,
                    risk_base_balance=risk_base_balance,
                    global_open_count=global_open_count,
                    max_open_positions=config.MAX_OPEN_POSITIONS,
                    base_risk=base_risk,
                    effective_risk=effective_risk,
                    risk_multiplier=risk_decision.multiplier,
                    risk_reasons=risk_decision.reasons,
                    price=price,
                    atr=atr,
                )
                if risk_decision.block_new_entries:
                    log.warning(
                        f"[{sym}] Risk takvimi/haber olayi nedeniyle yeni pozisyon bloklandi: "
                        f"{', '.join(risk_decision.reasons)}"
                    )
                    decision_snapshot["status"] = "risk_blocked"
                    decision_snapshots.write_snapshot(decision_snapshot)
                    continue
                log.info(
                    f"[{sym}] Risk: base={config.RISK_PER_TRADE_PCT*100:.2f}% "
                    f"corr={base_risk*100:.2f}% "
                    f"x{risk_decision.multiplier:.2f} -> {effective_risk*100:.2f}% "
                    f"({', '.join(risk_decision.reasons) or 'normal'})"
                )

                # Atomik emir acma islemi, secili risk base'e gore boyutlar.
                result = om.open_position(
                    exchange, signal, risk_base_balance, atr, price,
                    risk_pct=effective_risk,
                )
                decision_snapshots.write_snapshot(
                    decision_snapshots.attach_order_result(decision_snapshot, result)
                )
                if result:
                    global_open_count += 1
                    active_positions[sym] = {
                        "side":         result["side"],
                        "entry":        result["entry"],
                        "sl":           result["sl"],
                        "hard_sl":      result.get("hard_sl"),
                        "liquidation_price": result.get("liquidation_price"),
                        "atr":          result.get("atr"),
                        "size":         result["size"],
                        "extreme":      result["entry"],
                        "sl_order_id":  result.get("sl_order_id"),
                    }
                    _persist_positions()
                    log.info(f"[{sym}] {signal.upper()} pozisyon başarıyla açıldı. Giriş: {result['entry']} SL: {result['sl']:.2f}")

            except Exception as e:
                log.error(f"[{sym}] Sembol islenirken hata: {e}", exc_info=True)

    except Exception as e:
        log.error(f"Beklenmedik hata: {e}", exc_info=True)


def reset_daily():
    global daily_start_bal, daily_stop_active
    daily_start_bal = None
    daily_stop_active = False
    log.info("Günlük bakiye sıfırlandı.")


if __name__ == "__main__":
    log.info("Portföy Botu başlatılıyor...")
    log.info(f"Mod: {'TESTNET' if config.TESTNET else 'CANLI'}")
    log.info(f"İzlenen Semboller: {config.SYMBOLS} | TF: {config.TIMEFRAME} | Kaldıraç: {config.LEVERAGE}x")

    # 4H mum kapanışını kaçırmamak için saatlik kontrol
    schedule.every(1).hours.do(run)
    schedule.every().day.at("00:01").do(reset_daily)

    run()  # ilk koşu

    while True:
        schedule.run_pending()
        time.sleep(30)
