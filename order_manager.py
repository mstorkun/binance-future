import logging
import ccxt
import config
import risk as r

log = logging.getLogger(__name__)

TRAIL_CALLBACK_RATE = 1.5  # Binance trailing stop callback %1.5


def set_leverage(exchange: ccxt.Exchange):
    try:
        exchange.set_leverage(config.LEVERAGE, config.SYMBOL)
    except ccxt.BaseError as e:
        log.warning(f"Kaldıraç ayarlanamadı (zaten ayarlı olabilir): {e}")


def _safe_close_market(exchange: ccxt.Exchange, side: str, size: float):
    """Hata durumunda kullanılan acil kapatma."""
    close_side = "sell" if side == "long" else "buy"
    try:
        exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=close_side,
            amount=size,
            params={"reduceOnly": True},
        )
    except Exception as e:
        log.error(f"ACIL KAPATMA BAŞARISIZ: {e}")


def open_position(exchange: ccxt.Exchange, side: str, balance: float, atr: float, price: float):
    """
    Atomik pozisyon açma:
    1. Market emir
    2. Initial SL kur — başarısız olursa pozisyonu hemen kapat
    Not: Trailing stop kullanılmıyor, çıkış check_exit ile bot tarafından kontrol ediliyor.
    """
    size = r.position_size(balance, atr, price)

    # Min notional kontrolü (Binance Futures BTC için ~100 USDT)
    notional = size * price
    if notional < 100:
        log.warning(f"Pozisyon çok küçük (notional={notional:.2f}<100), açılmadı.")
        return None

    initial_sl, _ = r.sl_tp_prices(price, atr, side)
    order_side = "buy" if side == "long" else "sell"
    sl_side    = "sell" if side == "long" else "buy"

    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=order_side,
            amount=size,
            params={"reduceOnly": False},
        )
        log.info(f"Pozisyon açıldı: {side.upper()} | miktar={size} | fiyat≈{price:.2f}")
    except ccxt.BaseError as e:
        log.error(f"Pozisyon açma hatası: {e}")
        return None

    # SL kur — başarısız olursa pozisyonu kapat (atomik)
    try:
        exchange.create_order(
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=size,
            params={"stopPrice": initial_sl, "reduceOnly": True},
        )
        log.info(f"Initial SL koyuldu: {initial_sl:.2f}")
    except ccxt.BaseError as e:
        log.error(f"SL kurulamadı, pozisyon ACIL KAPATILIYOR: {e}")
        _safe_close_market(exchange, side, size)
        return None

    return {"order": order, "size": size, "side": side, "entry": price, "sl": initial_sl}


def update_trailing_sl(exchange: ccxt.Exchange, position: dict, current_price: float, extreme: float):
    """Bot her döngüde trailing SL'i manuel günceller — Binance trailing emirine güvenmeyiz."""
    side  = position["side"]
    entry = position["entry"]
    size  = position["size"]
    cur_sl = position["sl"]

    if side == "long":
        gain = extreme - entry
        if gain <= 0:
            return
        new_sl = extreme - gain * 0.15  # %15 giveback
        if new_sl <= cur_sl:
            return
    else:
        gain = entry - extreme
        if gain <= 0:
            return
        new_sl = extreme + gain * 0.15
        if new_sl >= cur_sl:
            return

    # Eski SL'i iptal et, yenisini koy
    try:
        exchange.cancel_all_orders(config.SYMBOL)
        sl_side = "sell" if side == "long" else "buy"
        exchange.create_order(
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=size,
            params={"stopPrice": new_sl, "reduceOnly": True},
        )
        position["sl"] = new_sl
        log.info(f"Trailing SL güncellendi: {cur_sl:.2f} → {new_sl:.2f}")
    except ccxt.BaseError as e:
        log.error(f"Trailing SL güncelleme hatası: {e}")


def close_position_market(exchange: ccxt.Exchange, side: str, size: float):
    """Trend tersine döndüğünde pozisyonu market emirle kapat."""
    close_side = "sell" if side == "long" else "buy"
    try:
        exchange.cancel_all_orders(config.SYMBOL)
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


def close_all(exchange: ccxt.Exchange):
    try:
        exchange.cancel_all_orders(config.SYMBOL)
    except Exception as e:
        log.warning(f"Emir iptal hatası: {e}")
    positions = exchange.fetch_positions([config.SYMBOL])
    for pos in positions:
        contracts = float(pos.get("contracts") or 0)
        if contracts == 0:
            continue
        side = pos.get("side") or ("long" if contracts > 0 else "short")
        close_position_market(exchange, side, abs(contracts))
