import logging
import ccxt
import config
import risk as r

log = logging.getLogger(__name__)

TRAIL_CALLBACK_RATE = 3.0  # Binance trailing stop callback %3 (kazancın ~%30'u)


def set_leverage(exchange: ccxt.Exchange):
    exchange.set_leverage(config.LEVERAGE, config.SYMBOL)


def open_position(exchange: ccxt.Exchange, side: str, balance: float, atr: float, price: float):
    size = r.position_size(balance, atr, price)
    initial_sl, _ = r.sl_tp_prices(price, atr, side)
    order_side = "buy" if side == "long" else "sell"
    sl_side    = "sell" if side == "long" else "buy"

    try:
        # Pozisyon aç (market)
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=order_side,
            amount=size,
            params={"reduceOnly": False},
        )
        log.info(f"Pozisyon açıldı: {side.upper()} | miktar={size} | fiyat≈{price:.2f}")

        # İlk stop loss (market)
        exchange.create_order(
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=size,
            params={"stopPrice": initial_sl, "reduceOnly": True},
        )
        log.info(f"İlk SL koyuldu: {initial_sl:.2f}")

        # Trailing stop (Binance otomatik takip eder)
        exchange.create_order(
            symbol=config.SYMBOL,
            type="trailing_stop_market",
            side=sl_side,
            amount=size,
            params={
                "callbackRate": TRAIL_CALLBACK_RATE,
                "reduceOnly": True,
                "activationPrice": price,
            },
        )
        log.info(f"Trailing stop koyuldu: callback=%{TRAIL_CALLBACK_RATE}")

        return order

    except ccxt.BaseError as e:
        log.error(f"Emir hatası: {e}")
        return None


def close_position_market(exchange: ccxt.Exchange, side: str, size: float):
    """Trend tersine döndüğünde pozisyonu market emirle kapat."""
    close_side = "sell" if side == "long" else "buy"
    try:
        exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=close_side,
            amount=size,
            params={"reduceOnly": True},
        )
        log.info(f"Pozisyon kapatıldı (trend exit): {side.upper()}")
    except ccxt.BaseError as e:
        log.error(f"Kapatma hatası: {e}")


def cancel_open_orders(exchange: ccxt.Exchange):
    """Açık SL/TP emirlerini iptal et."""
    try:
        exchange.cancel_all_orders(config.SYMBOL)
        log.info("Açık emirler iptal edildi.")
    except ccxt.BaseError as e:
        log.error(f"Emir iptali hatası: {e}")


def close_all(exchange: ccxt.Exchange):
    cancel_open_orders(exchange)
    positions = exchange.fetch_positions([config.SYMBOL])
    for pos in positions:
        contracts = float(pos["contracts"])
        if contracts == 0:
            continue
        close_position_market(exchange, pos["side"], abs(contracts))
