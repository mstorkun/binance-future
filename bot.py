"""
Canlı bot ana döngüsü.

Mimari sözleşme:
    data           : exchange + ohlcv + bakiye + pozisyon sorgusu
    indicators     : EMA / ADX / RSI / ATR (Wilder)
    strategy       : get_signal, check_exit, trailing_stop
    risk           : pozisyon boyutu, SL/TP fiyatları, günlük kayıp limiti
    order_manager  : atomik pozisyon açma, trailing SL update, market kapama

Akış:
  1. Bakiye + günlük kayıp kontrolü
  2. OHLCV + indikatör hesabı
  3. Borsa pozisyon state'ini sorgula (otorite kaynak)
  4. Açık pozisyon var → check_exit (trend tersine döndü mü?) veya trailing SL update
  5. Açık pozisyon yok → get_signal → varsa open_position (atomik)
"""

import time
import logging
import schedule

import config
import data
import indicators as ind
import strategy as strat
import risk as r
import order_manager as om


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
active_position  = None    # {"side", "entry", "sl", "size", "extreme"}


def _has_open_position() -> dict | None:
    """Sembolde gerçek açık pozisyon var mı? Borsa state'i otorite."""
    try:
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

    real_sl, sl_order_id = om.fetch_active_sl(exchange)
    if real_sl is not None:
        sl = real_sl
        log.info(f"State recovery: borsadaki SL bulundu = {sl:.2f}")
    else:
        atr = float(df["atr"].iloc[-2])
        sl, _ = r.sl_tp_prices(entry, atr, side)
        sl_order_id = None
        log.warning(f"State recovery: borsada SL bulunamadı, ATR ile tahmin = {sl:.2f}")

    log.info(f"State recovery: {side.upper()} entry={entry:.2f} size={abs(contracts)}")
    return {
        "side":         side,
        "entry":        entry,
        "sl":           sl,
        "size":         abs(contracts),
        "extreme":      entry,
        "sl_order_id":  sl_order_id,
    }


def run():
    global daily_start_bal, active_position
    log.info("--- Döngü başladı ---")

    try:
        # 1. Bakiye + günlük kayıp limiti
        balance = data.fetch_balance(exchange)
        log.info(f"Bakiye: {balance:.2f} USDT")

        if daily_start_bal is None:
            daily_start_bal = balance

        if r.daily_loss_exceeded(daily_start_bal, balance):
            log.warning("Günlük kayıp limiti! Tüm pozisyonlar kapatılıyor, bot duruyor.")
            om.close_all(exchange)
            active_position = None
            return

        # 2. Veri + indikatörler (4H + 1D)
        df    = data.fetch_ohlcv(exchange)
        df_1d = data.fetch_daily_ohlcv(exchange, limit=200)
        df    = ind.add_indicators(df)
        df    = ind.add_daily_trend(df, df_1d)
        if len(df) < 3:
            log.warning("Yeterli mum yok.")
            return

        # 3. Borsa pozisyon state'i
        live_pos = _has_open_position()

        # 4a. Açık pozisyon var
        if live_pos:
            if active_position is None:
                active_position = _recover_position(live_pos, df)

            cur_price = float(df["close"].iloc[-1])

            # Trend tersine döndü mü?
            if strat.check_exit(df, active_position["side"]):
                log.info(f"Trend tersine döndü → {active_position['side'].upper()} kapatılıyor.")
                om.close_position_market(exchange, active_position["side"], active_position["size"])
                active_position = None
                return

            # Extreme güncelle
            if active_position["side"] == strat.LONG:
                active_position["extreme"] = max(active_position["extreme"], cur_price)
            else:
                active_position["extreme"] = min(active_position["extreme"], cur_price)

            # Trailing SL hesapla ve gerekirse borsada güncelle
            om.update_trailing_sl(exchange, active_position, cur_price, active_position["extreme"])
            return

        # 4b. Açık pozisyon yok — bot state'i temizle, yeni sinyal ara
        if active_position is not None:
            log.info("Pozisyon dışarıda kapanmış (SL veya manuel).")
            active_position = None

        signal = strat.get_signal(df)
        log.info(f"Sinyal: {signal or 'YOK'}")
        if signal is None:
            return

        # 5. Yeni pozisyon aç
        price = float(df["close"].iloc[-2])   # son kapanan bar
        atr   = float(df["atr"].iloc[-2])

        # set_leverage open_position içinde yapılıyor, başarısızsa pozisyon açılmaz
        result = om.open_position(exchange, signal, balance, atr, price)
        if result:
            active_position = {
                "side":         result["side"],
                "entry":        result["entry"],
                "sl":           result["sl"],
                "size":         result["size"],
                "extreme":      result["entry"],
                "sl_order_id":  result.get("sl_order_id"),
            }

    except Exception as e:
        log.error(f"Beklenmedik hata: {e}", exc_info=True)


def reset_daily():
    global daily_start_bal
    daily_start_bal = None
    log.info("Günlük bakiye sıfırlandı.")


if __name__ == "__main__":
    log.info("Bot başlatılıyor...")
    log.info(f"Mod: {'TESTNET' if config.TESTNET else 'CANLI'}")
    log.info(f"Sembol: {config.SYMBOL} | TF: {config.TIMEFRAME} | Kaldıraç: {config.LEVERAGE}x")

    # 4H mum kapanışını kaçırmamak için saatlik kontrol
    schedule.every(1).hours.do(run)
    schedule.every().day.at("00:01").do(reset_daily)

    run()  # ilk koşu

    while True:
        schedule.run_pending()
        time.sleep(30)
