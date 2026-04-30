import logging
import ccxt
import config
import risk as r

log = logging.getLogger(__name__)

MIN_NOTIONAL_USDT = 100  # Binance Futures BTC min notional ~100 USDT


def set_leverage(exchange: ccxt.Exchange) -> bool:
    """Kaldıracı ayarla. Başarısızsa False döner — pozisyon açma iptal edilmeli."""
    try:
        exchange.set_leverage(config.LEVERAGE, config.SYMBOL)
        return True
    except ccxt.BaseError as e:
        msg = str(e).lower()
        # "no need to change" gibi hatalar zaten ayarlı demektir, başarı say
        if "no need" in msg or "not modified" in msg:
            return True
        log.error(f"Kaldıraç ayarlanamadı: {e}")
        return False


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


def _amount_to_precision(exchange: ccxt.Exchange, size: float) -> float:
    """Binance lot size'a uydur."""
    try:
        return float(exchange.amount_to_precision(config.SYMBOL, size))
    except Exception:
        return round(size, 4)


def _create_sl_order(exchange: ccxt.Exchange, sl_side: str, size: float, sl_price: float) -> dict | None:
    """SL emri oluştur — emrin id'sini döndürür."""
    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=size,
            params={"stopPrice": sl_price, "reduceOnly": True},
        )
        return order
    except ccxt.BaseError as e:
        log.error(f"SL emir hatası: {e}")
        return None


def _cancel_order_safe(exchange: ccxt.Exchange, order_id: str):
    try:
        exchange.cancel_order(order_id, config.SYMBOL)
    except Exception as e:
        log.warning(f"SL iptal hatası (zaten iptal/dolu olabilir): {e}")


def open_position(exchange: ccxt.Exchange, side: str, balance: float, atr: float, price: float):
    """
    Atomik pozisyon açma:
    1. Kaldıracı ayarla (başarısızsa abort)
    2. Min notional kontrol
    3. Market emir
    4. Initial SL kur — başarısız olursa pozisyonu hemen kapat
    """
    if not set_leverage(exchange):
        log.error("Kaldıraç ayarsız, pozisyon açma iptal edildi.")
        return None

    size = r.position_size(balance, atr, price)
    size = _amount_to_precision(exchange, size)

    notional = size * price
    if notional < MIN_NOTIONAL_USDT:
        log.warning(f"Pozisyon çok küçük (notional={notional:.2f}<{MIN_NOTIONAL_USDT}), açılmadı.")
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

    sl_order = _create_sl_order(exchange, sl_side, size, initial_sl)
    if sl_order is None:
        log.error("SL kurulamadı, pozisyon ACIL KAPATILIYOR.")
        _safe_close_market(exchange, side, size)
        return None
    log.info(f"Initial SL koyuldu: {initial_sl:.2f}")

    return {
        "order":     order,
        "size":      size,
        "side":      side,
        "entry":     price,
        "sl":        initial_sl,
        "sl_order_id": sl_order.get("id"),
    }


def update_trailing_sl(exchange: ccxt.Exchange, position: dict, current_price: float, extreme: float):
    """
    Trailing SL güncellemesi — race condition önleyici sıra:
    1. Yeni SL emrini OLUŞTUR (her iki SL kısa süre birlikte yaşar — pozisyon korumasız KALMAZ)
    2. Eski SL emrini İPTAL ET
    3. State'te yeni emir id'sini sakla
    """
    side  = position["side"]
    entry = position["entry"]
    size  = position["size"]
    cur_sl = position["sl"]
    old_sl_id = position.get("sl_order_id")

    if side == "long":
        gain = extreme - entry
        if gain <= 0:
            return
        new_sl = extreme - gain * 0.15
        if new_sl <= cur_sl:
            return
    else:
        gain = entry - extreme
        if gain <= 0:
            return
        new_sl = extreme + gain * 0.15
        if new_sl >= cur_sl:
            return

    sl_side = "sell" if side == "long" else "buy"

    # Önce yeni emri oluştur — pozisyon her an korunsun
    new_sl_order = _create_sl_order(exchange, sl_side, size, new_sl)
    if new_sl_order is None:
        log.error("Yeni trailing SL oluşturulamadı, eski SL korunuyor.")
        return

    # Sonra eski emri iptal et
    if old_sl_id:
        _cancel_order_safe(exchange, old_sl_id)

    position["sl"] = new_sl
    position["sl_order_id"] = new_sl_order.get("id")
    log.info(f"Trailing SL güncellendi: {cur_sl:.2f} → {new_sl:.2f}")


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


def fetch_active_sl(exchange: ccxt.Exchange) -> tuple[float | None, str | None]:
    """Borsada aktif SL emrini çek — state recovery için."""
    try:
        orders = exchange.fetch_open_orders(config.SYMBOL)
    except Exception as e:
        log.warning(f"Açık emir sorgusu başarısız: {e}")
        return None, None

    for o in orders:
        otype = (o.get("type") or "").lower()
        if "stop" in otype and o.get("reduceOnly"):
            stop_price = o.get("stopPrice") or o.get("triggerPrice")
            if stop_price:
                return float(stop_price), o.get("id")
    return None, None
