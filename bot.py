"""
Ana bot döngüsü.
Kullanım:
    python bot.py
"""

import time
import logging
import schedule
import data
import indicators as ind
import strategy as strat
import risk as r
import order_manager as om
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

exchange       = data.make_exchange()
daily_start_bal = None


def run():
    global daily_start_bal

    log.info("--- Döngü başladı ---")

    try:
        balance = data.fetch_balance(exchange)
        log.info(f"Bakiye: {balance:.2f} USDT")

        # Günlük sıfırlama (UTC 00:00)
        if daily_start_bal is None:
            daily_start_bal = balance

        # Günlük kayıp limiti kontrolü
        if r.daily_loss_exceeded(daily_start_bal, balance):
            log.warning("Günlük kayıp limitine ulaşıldı! Bot durduruldu.")
            om.close_all(exchange)
            return

        # Açık pozisyon sayısı kontrolü
        open_pos = data.fetch_open_positions(exchange)
        if len(open_pos) >= config.MAX_OPEN_POSITIONS:
            log.info(f"Max pozisyon limitinde ({len(open_pos)}), yeni işlem açılmıyor.")
            return

        # Veri + indikatör
        df = data.fetch_ohlcv(exchange)
        df = ind.add_indicators(df)

        if len(df) < 3:
            log.warning("Yeterli veri yok.")
            return

        # Sinyal
        signal = strat.get_signal(df)
        log.info(f"Sinyal: {signal or 'YOK'}")

        if signal is None:
            return

        # Güncel fiyat ve ATR
        price = float(df["close"].iloc[-2])
        atr   = float(df["atr"].iloc[-2])

        # Kaldıraç ayarla
        om.set_leverage(exchange)

        # Emir aç
        om.open_position(exchange, signal, balance, atr, price)

    except Exception as e:
        log.error(f"Beklenmedik hata: {e}", exc_info=True)


def reset_daily():
    global daily_start_bal
    daily_start_bal = None
    log.info("Günlük bakiye sıfırlandı.")


if __name__ == "__main__":
    log.info("Bot başlatılıyor...")
    log.info(f"Mod: {'TESTNET' if config.TESTNET else 'CANLI'}")
    log.info(f"Sembol: {config.SYMBOL} | Zaman dilimi: {config.TIMEFRAME} | Kaldıraç: {config.LEVERAGE}x")

    # 4 saatlik mumla senkron: her 4 saatte bir çalış
    schedule.every(4).hours.do(run)
    schedule.every().day.at("00:01").do(reset_daily)

    run()  # başlangıçta bir kez çalıştır

    while True:
        schedule.run_pending()
        time.sleep(30)
