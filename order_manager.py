import logging
import ccxt
import config
import risk as r

log = logging.getLogger(__name__)


def set_leverage(exchange: ccxt.Exchange):
    exchange.set_leverage(config.LEVERAGE, config.SYMBOL)


def open_position(exchange: ccxt.Exchange, side: str, balance: float, atr: float, price: float):
    size = r.position_size(balance, atr, price)
    sl, tp = r.sl_tp_prices(price, atr, side)

    order_side = "buy" if side == "long" else "sell"

    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=order_side,
            amount=size,
            params={"reduceOnly": False},
        )
        log.info(f"Pozisyon açıldı: {side.upper()} | miktar={size} | fiyat≈{price:.2f} | SL={sl} | TP={tp}")

        # SL emri
        sl_side = "sell" if side == "long" else "buy"
        exchange.create_order(
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=size,
            params={"stopPrice": sl, "reduceOnly": True},
        )

        # TP emri
        exchange.create_order(
            symbol=config.SYMBOL,
            type="take_profit_market",
            side=sl_side,
            amount=size,
            params={"stopPrice": tp, "reduceOnly": True},
        )

        return order
    except ccxt.BaseError as e:
        log.error(f"Emir hatası: {e}")
        return None


def close_all(exchange: ccxt.Exchange):
    positions = exchange.fetch_positions([config.SYMBOL])
    for pos in positions:
        contracts = float(pos["contracts"])
        if contracts == 0:
            continue
        side = "sell" if pos["side"] == "long" else "buy"
        try:
            exchange.create_order(
                symbol=config.SYMBOL,
                type="market",
                side=side,
                amount=abs(contracts),
                params={"reduceOnly": True},
            )
            log.info(f"Pozisyon kapatıldı: {pos['side'].upper()} | miktar={contracts}")
        except ccxt.BaseError as e:
            log.error(f"Kapatma hatası: {e}")
