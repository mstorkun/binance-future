import logging
import ccxt
import account_safety
import config
import execution_guard as eg
import exchange_filters as xf
import liquidation
import order_events
import risk as r

log = logging.getLogger(__name__)

MIN_NOTIONAL_USDT = 100  # Binance Futures BTC min notional ~100 USDT


def ensure_one_way_mode(exchange: ccxt.Exchange) -> bool:
    """Bot reduceOnly stop logic assumes Binance one-way position mode."""
    if not getattr(config, "REQUIRE_ONE_WAY_MODE", True):
        return True
    status = account_safety.position_mode_status(exchange)
    if not status["ok"]:
        log.error(f"Pozisyon modu uygun degil, pozisyon acma iptal: {status['reason']}")
        return False
    return True


def set_leverage(exchange: ccxt.Exchange) -> bool:
    """Kaldıracı ayarla. Başarısızsa False döner — pozisyon açma iptal edilmeli."""
    try:
        response = exchange.set_leverage(config.LEVERAGE, config.SYMBOL)
        if not account_safety.confirm_set_leverage_response(response, config.LEVERAGE):
            log.error(f"Kaldirac cevabi hedefle uyusmuyor: hedef={config.LEVERAGE}, cevap={response}")
            return False
        return True
    except ccxt.BaseError as e:
        msg = str(e).lower()
        # "no need to change" gibi hatalar zaten ayarlı demektir, başarı say
        if "no need" in msg or "not modified" in msg:
            return True
        log.error(f"Kaldıraç ayarlanamadı: {e}")
        return False


def set_margin_mode(exchange: ccxt.Exchange) -> bool:
    """Margin mode'u config ile uyumlu hale getir. Basarisizsa pozisyon acma iptal edilir."""
    desired = getattr(config, "MARGIN_MODE", "cross")
    try:
        response = exchange.set_margin_mode(desired, config.SYMBOL)
        if not account_safety.confirm_set_margin_mode_response(response, desired):
            log.error(f"Margin mode cevabi hedefle uyusmuyor: hedef={desired}, cevap={response}")
            return False
        return True
    except ccxt.BaseError as e:
        msg = str(e).lower()
        if "no need" in msg or "not modified" in msg or "already" in msg:
            return True
        log.error(f"Margin mode ayarlanamadi: {e}")
        return False


def _safe_close_market(exchange: ccxt.Exchange, side: str, size: float):
    """Hata durumunda kullanılan acil kapatma."""
    close_side = "sell" if side == "long" else "buy"
    order_events.record("emergency_close_submit", side=close_side, amount=size, reduce_only=True)
    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=close_side,
            amount=size,
            params={"reduceOnly": True},
        )
        order_events.record("emergency_close_ack", order=order_events.extract_order_summary(order))
    except Exception as e:
        order_events.record("emergency_close_error", error=str(e))
        log.error(f"ACIL KAPATMA BAŞARISIZ: {e}")


def _amount_to_precision(exchange: ccxt.Exchange, size: float) -> float:
    """Binance lot size'a uydur."""
    try:
        return float(exchange.amount_to_precision(config.SYMBOL, size))
    except Exception:
        return round(size, 4)


def _create_sl_order(
    exchange: ccxt.Exchange,
    sl_side: str,
    size: float,
    sl_price: float,
    ref_price: float | None = None,
) -> dict | None:
    """SL emri oluştur — emrin id'sini döndürür."""
    filter_result = xf.validate_stop_order(
        exchange,
        config.SYMBOL,
        sl_side,
        size,
        sl_price,
        ref_price=ref_price or sl_price,
    )
    if not filter_result.ok:
        order_events.record(
            "stop_order_filter_block",
            side=sl_side,
            amount=size,
            stop_price=sl_price,
            reason=filter_result.reason,
        )
        log.error(f"SL emir filtre hatasi: {filter_result.reason}")
        return None

    checked_size = filter_result.amount or size
    checked_sl_price = filter_result.price or sl_price
    order_events.record(
        "stop_order_submit",
        side=sl_side,
        amount=checked_size,
        stop_price=checked_sl_price,
        ref_price=ref_price,
    )
    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=checked_size,
            params=eg.exchange_stop_params(checked_sl_price),
        )
        order_events.record("stop_order_ack", order=order_events.extract_order_summary(order))
        return order
    except ccxt.BaseError as e:
        order_events.record("stop_order_error", side=sl_side, amount=checked_size, stop_price=checked_sl_price, error=str(e))
        log.error(f"SL emir hatası: {e}")
        return None


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _order_avg_price(order: dict | None, fallback: float) -> float:
    if not order:
        return fallback
    info = order.get("info") or {}
    for key in ("average", "avgPrice", "price"):
        value = _num(order.get(key))
        if value:
            return value
    for key in ("avgPrice", "price"):
        value = _num(info.get(key))
        if value:
            return value

    filled = _num(order.get("filled")) or _num(info.get("executedQty"))
    cost = _num(order.get("cost")) or _num(info.get("cumQuote"))
    if filled and cost:
        return cost / filled
    return fallback


def _order_filled_amount(order: dict | None, fallback: float) -> float:
    if not order:
        return fallback
    info = order.get("info") or {}
    return _num(order.get("filled")) or _num(info.get("executedQty")) or fallback


def _resolve_market_fill(
    exchange: ccxt.Exchange,
    order: dict | None,
    fallback_price: float,
    fallback_size: float,
    context: str = "market",
) -> tuple[float, float]:
    price = _order_avg_price(order, fallback_price)
    size = _order_filled_amount(order, fallback_size)
    order_id = order.get("id") if order else None
    if order_id and (price == fallback_price or size == fallback_size):
        try:
            fetched = exchange.fetch_order(order_id, config.SYMBOL)
            order_events.record(f"{context}_order_fetch", order=order_events.extract_order_summary(fetched))
            price = _order_avg_price(fetched, price)
            size = _order_filled_amount(fetched, size)
        except Exception as e:
            order_events.record(f"{context}_order_fetch_error", order_id=order_id, error=str(e))
            log.warning(f"Market fill detayi cekilemedi, ilk order cevabi kullaniliyor: {e}")
    order_events.record(
        f"{context}_fill_resolved",
        order_id=order_id,
        fallback_price=fallback_price,
        fallback_size=fallback_size,
        fill_price=price,
        filled_size=size,
    )
    return price, size


def _cancel_order_safe(exchange: ccxt.Exchange, order_id: str):
    order_events.record("order_cancel_submit", order_id=order_id)
    try:
        exchange.cancel_order(order_id, config.SYMBOL)
        order_events.record("order_cancel_ack", order_id=order_id)
    except Exception as e:
        order_events.record("order_cancel_error", order_id=order_id, error=str(e))
        log.warning(f"SL iptal hatası (zaten iptal/dolu olabilir): {e}")


def open_position(exchange: ccxt.Exchange, side: str, balance: float, atr: float, price: float,
                  risk_pct: float | None = None):
    """
    Atomik pozisyon açma:
    1. Kaldıracı ayarla (başarısızsa abort)
    2. Min notional kontrol
    3. Market emir
    4. Initial SL kur — başarısız olursa pozisyonu hemen kapat
    """
    if not ensure_one_way_mode(exchange):
        return None

    if not set_margin_mode(exchange):
        log.error("Margin mode dogrulanamadi, pozisyon acma iptal edildi.")
        return None

    if not set_leverage(exchange):
        log.error("Kaldıraç ayarsız, pozisyon açma iptal edildi.")
        return None

    size = r.position_size(balance, atr, price, risk_pct=risk_pct)
    size = _amount_to_precision(exchange, size)

    order_side = "buy" if side == "long" else "sell"
    sl_side    = "sell" if side == "long" else "buy"

    filter_result = xf.validate_entry_order(exchange, config.SYMBOL, order_side, size, price)
    if not filter_result.ok:
        order_events.record(
            "entry_order_filter_block",
            side=order_side,
            amount=size,
            ref_price=price,
            reason=filter_result.reason,
        )
        log.warning(f"Exchange filtreleri pozisyonu blokladi: {filter_result.reason}")
        return None
    size = filter_result.amount or size
    notional = filter_result.notional or (size * price)

    initial_sl, _ = r.sl_tp_prices(price, atr, side)
    hard_sl = eg.hard_stop_from_soft(initial_sl, atr, side)
    liq_guard = liquidation.liquidation_guard_decision(price, side, hard_sl, leverage=config.LEVERAGE)
    if not liq_guard.ok:
        log.warning(f"Likidasyon guard pozisyonu blokladi: {liq_guard.reason}")
        return None

    guard = eg.pre_trade_liquidity_check(exchange, config.SYMBOL, side, notional, price)
    if not guard.ok:
        order_events.record("entry_order_guard_block", side=order_side, amount=size, notional=notional, reason=guard.reason)
        log.warning(f"Likidite/spread guard pozisyonu blokladi: {guard.reason}")
        return None

    order_events.record(
        "entry_order_submit",
        side=order_side,
        strategy_side=side,
        amount=size,
        notional=notional,
        ref_price=price,
        atr=atr,
        risk_pct=risk_pct,
    )
    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=order_side,
            amount=size,
            params={
                "reduceOnly": False,
                "newOrderRespType": getattr(config, "MARKET_ORDER_RESP_TYPE", "RESULT"),
            },
        )
        order_events.record("entry_order_ack", order=order_events.extract_order_summary(order))
        log.info(f"Pozisyon açıldı: {side.upper()} | miktar={size} | fiyat≈{price:.2f}")
    except ccxt.BaseError as e:
        order_events.record("entry_order_error", side=order_side, amount=size, error=str(e))
        log.error(f"Pozisyon açma hatası: {e}")
        return None

    fill_price, filled_size = _resolve_market_fill(exchange, order, price, size, context="entry")
    initial_sl, _ = r.sl_tp_prices(fill_price, atr, side)
    hard_sl = eg.hard_stop_from_soft(initial_sl, atr, side)
    liq_guard = liquidation.liquidation_guard_decision(fill_price, side, hard_sl, leverage=config.LEVERAGE)
    if not liq_guard.ok:
        order_events.record(
            "post_fill_liquidation_guard_block",
            side=side,
            fill_price=fill_price,
            filled_size=filled_size,
            hard_sl=hard_sl,
            reason=liq_guard.reason,
        )
        log.error(f"Fill sonrasi likidasyon guard bozuldu, pozisyon kapatiliyor: {liq_guard.reason}")
        _safe_close_market(exchange, side, filled_size)
        return None

    log.info(f"Pozisyon acildi: {side.upper()} | miktar={filled_size} | fill={fill_price:.4f}")

    sl_order = _create_sl_order(exchange, sl_side, filled_size, hard_sl, ref_price=fill_price)
    if sl_order is None:
        order_events.record("entry_stop_missing_emergency_close", side=side, filled_size=filled_size)
        log.error("SL kurulamadı, pozisyon ACIL KAPATILIYOR.")
        _safe_close_market(exchange, side, filled_size)
        return None
    log.info(f"Hard SL koyuldu: {hard_sl:.2f} | Soft SL: {initial_sl:.2f}")

    return {
        "order":     order,
        "size":      filled_size,
        "side":      side,
        "entry":     fill_price,
        "sl":        initial_sl,
        "hard_sl":   hard_sl,
        "liquidation_price": liq_guard.liquidation_price,
        "atr":       atr,
        "sl_order_id": sl_order.get("id"),
    }


def update_trailing_sl(exchange: ccxt.Exchange, position: dict, current_price: float, extreme: float, bar=None):
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
    atr = float(position.get("atr") or 0)

    if bar is not None:
        guard = eg.should_skip_trailing_update(bar)
        if not guard.ok:
            log.info(f"Trailing SL guncellemesi atlandi: {guard.reason}")
            return

    if side == "long":
        gain = extreme - entry
        if gain <= 0:
            return
        giveback = config.TRAIL_GIVEBACK
        risk_dist = atr * config.SL_ATR_MULT if atr > 0 else 0
        if risk_dist > 0 and gain >= risk_dist * getattr(config, "TRAIL_WIDE_AFTER_R", 2.5):
            giveback = max(giveback, getattr(config, "TRAIL_GIVEBACK_STRONG", giveback))
        new_sl = extreme - gain * giveback
        if new_sl <= cur_sl:
            return
    else:
        gain = entry - extreme
        if gain <= 0:
            return
        giveback = config.TRAIL_GIVEBACK
        risk_dist = atr * config.SL_ATR_MULT if atr > 0 else 0
        if risk_dist > 0 and gain >= risk_dist * getattr(config, "TRAIL_WIDE_AFTER_R", 2.5):
            giveback = max(giveback, getattr(config, "TRAIL_GIVEBACK_STRONG", giveback))
        new_sl = extreme + gain * giveback
        if new_sl >= cur_sl:
            return

    sl_side = "sell" if side == "long" else "buy"

    hard_sl = eg.hard_stop_from_soft(new_sl, atr, side) if atr > 0 else new_sl

    # Önce yeni hard-stop emrini oluştur — pozisyon her an korunsun
    new_sl_order = _create_sl_order(exchange, sl_side, size, hard_sl, ref_price=current_price)
    if new_sl_order is None:
        log.error("Yeni trailing SL oluşturulamadı, eski SL korunuyor.")
        return

    # Sonra eski emri iptal et
    if old_sl_id:
        _cancel_order_safe(exchange, old_sl_id)

    position["sl"] = new_sl
    position["hard_sl"] = hard_sl
    position["sl_order_id"] = new_sl_order.get("id")
    log.info(f"Trailing soft SL guncellendi: {cur_sl:.2f} -> {new_sl:.2f} | hard={hard_sl:.2f}")


def close_position_market(exchange: ccxt.Exchange, side: str, size: float) -> bool:
    """Fail-safe reduce-only market close; cancel failures do not block close."""
    close_side = "sell" if side == "long" else "buy"
    try:
        exchange.cancel_all_orders(config.SYMBOL)
        order_events.record("close_cancel_all_ack")
    except ccxt.BaseError as e:
        order_events.record("close_cancel_all_error", error=str(e))
        log.warning(f"Kapatma oncesi emir iptali basarisiz, market close yine denenecek: {e}")

    order_events.record("close_order_submit", side=close_side, amount=size, reduce_only=True)
    try:
        order = exchange.create_order(
            symbol=config.SYMBOL,
            type="market",
            side=close_side,
            amount=size,
            params={"reduceOnly": True},
        )
        order_events.record("close_order_ack", order=order_events.extract_order_summary(order))
        fill_price, filled_size = _resolve_market_fill(exchange, order, 0.0, size, context="close")
        log.info(f"Pozisyon kapatildi (trend exit): {side.upper()} | miktar={filled_size} | fill={fill_price:.4f}")
        return True
    except ccxt.BaseError as e:
        order_events.record("close_order_error", side=close_side, amount=size, error=str(e))
        log.error(f"Kapatma hatasi: {e}")
        return False


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
