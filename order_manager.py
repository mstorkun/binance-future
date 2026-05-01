import logging
import secrets
import time
from dataclasses import dataclass

import ccxt
import account_safety
import config
import execution_guard as eg
import exchange_filters as xf
import liquidation
import order_events
import risk as r

log = logging.getLogger(__name__)

INTENT_ALIASES = {
    "entry": "entry",
    "hard_sl": "hard_sl",
    "trailing_sl": "trail_sl",
    "trail_sl": "trail_sl",
    "close": "close",
    "emergency_close": "eclose",
    "eclose": "eclose",
}


@dataclass(frozen=True)
class FillResolution:
    fill_price: float
    filled_size: float
    requested_size: float
    remaining_size: float
    partial: bool
    aborted: bool
    order_id: str | None = None
    client_order_id: str | None = None
    status: str | None = None

    def __iter__(self):
        yield self.fill_price
        yield self.filled_size


def signed_params(extra: dict | None = None) -> dict:
    params = {"recvWindow": int(getattr(config, "RECV_WINDOW_MS", 5000))}
    if extra:
        params.update(extra)
    return params


def _symbol_short(symbol: str) -> str:
    base = symbol.replace("/", "").replace(":", "").replace("-", "").upper()
    for suffix in ("USDT", "USDC", "BUSD", "USD"):
        if base.endswith(suffix) and len(base) > len(suffix):
            base = base[: -len(suffix)]
            break
    return "".join(ch for ch in base if ch.isalnum())[:8] or "SYMBOL"


def client_order_id(
    symbol: str,
    intent: str,
    *,
    epoch_ms: int | None = None,
    nonce8: str | None = None,
) -> str:
    ts = int(epoch_ms if epoch_ms is not None else time.time() * 1000)
    nonce = (nonce8 or secrets.token_hex(4))[:8]
    intent_short = INTENT_ALIASES.get(intent, intent)
    intent_short = "".join(ch for ch in intent_short if ch.isalnum() or ch == "_")[:8] or "order"
    max_symbol_len = max(1, 36 - len(str(ts)) - len(intent_short) - len(nonce) - 3)
    symbol_short = _symbol_short(symbol)[:max_symbol_len]
    return f"{symbol_short}_{ts}_{intent_short}_{nonce}"


def _client_order_id_from_order(order: dict | None) -> str | None:
    if not order:
        return None
    info = order.get("info") or {}
    return order.get("clientOrderId") or order.get("client_order_id") or info.get("clientOrderId")


def _exchange_symbol_id(exchange: ccxt.Exchange, symbol: str) -> str:
    try:
        return exchange.market_id(symbol)
    except Exception:
        return symbol.replace("/", "")


def _is_duplicate_client_order_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in (
        "duplicate",
        "duplicated",
        "already exists",
        "already exist",
        "client order id already",
        "clientorderid already",
    ))


def _fetch_order_by_client_id(exchange: ccxt.Exchange, client_order_id_value: str, symbol: str | None = None) -> dict:
    symbol = symbol or config.SYMBOL
    params = signed_params({"origClientOrderId": client_order_id_value})
    raw_get_order = getattr(exchange, "fapiPrivateGetOrder", None)
    if raw_get_order is not None:
        raw = raw_get_order({
            "symbol": _exchange_symbol_id(exchange, symbol),
            "origClientOrderId": client_order_id_value,
            **params,
        })
        return {
            "id": raw.get("orderId"),
            "clientOrderId": raw.get("clientOrderId") or client_order_id_value,
            "status": raw.get("status"),
            "info": raw,
        }
    try:
        return exchange.fetch_order(None, symbol, params)
    except Exception as first_exc:
        raise first_exc


def _create_order_idempotent(
    exchange: ccxt.Exchange,
    *,
    symbol: str,
    type: str,
    side: str,
    amount: float,
    intent: str,
    params: dict | None = None,
    client_order_id_value: str | None = None,
) -> tuple[dict, str, bool]:
    cid = client_order_id_value or client_order_id(symbol, intent)
    full_params = signed_params({**(params or {}), "newClientOrderId": cid})
    attempts = max(1, int(getattr(config, "CREATE_ORDER_MAX_RETRIES", 2)))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            order = exchange.create_order(
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                params=full_params,
            )
            return order, cid, False
        except (ccxt.RequestTimeout, ccxt.NetworkError) as exc:
            last_error = exc
            order_events.record(
                "create_order_retry",
                intent=intent,
                side=side,
                amount=amount,
                client_order_id=cid,
                attempt=attempt,
                error=str(exc),
            )
            if attempt < attempts:
                continue
            try:
                fetched = _fetch_order_by_client_id(exchange, cid, symbol)
                order_events.record(
                    "create_order_timeout_reconciled",
                    intent=intent,
                    client_order_id=cid,
                    order=order_events.extract_order_summary(fetched),
                )
                return fetched, cid, True
            except Exception as fetch_exc:
                order_events.record(
                    "create_order_timeout_reconcile_error",
                    intent=intent,
                    client_order_id=cid,
                    error=str(fetch_exc),
                )
            raise
        except ccxt.BaseError as exc:
            if not _is_duplicate_client_order_error(exc):
                raise
            order_events.record(
                "create_order_duplicate_detected",
                intent=intent,
                side=side,
                amount=amount,
                client_order_id=cid,
                error=str(exc),
            )
            fetched = _fetch_order_by_client_id(exchange, cid, symbol)
            order_events.record(
                "create_order_duplicate_reconciled",
                intent=intent,
                client_order_id=cid,
                order=order_events.extract_order_summary(fetched),
            )
            return fetched, cid, True
    raise last_error or RuntimeError("create order failed without exception")


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
        response = exchange.set_leverage(config.LEVERAGE, config.SYMBOL, signed_params())
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
        response = exchange.set_margin_mode(desired, config.SYMBOL, signed_params())
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
    checked_size = _reduce_only_market_amount(exchange, size, "emergency_close")
    if checked_size is None:
        log.error("Acil kapatma miktari exchange filtrelerinden gecemedi.")
        return
    cid = client_order_id(config.SYMBOL, "emergency_close")
    order_events.record("emergency_close_submit", side=close_side, amount=checked_size, requested_amount=size, reduce_only=True, client_order_id=cid)
    try:
        order, resolved_cid, duplicate = _create_order_idempotent(
            exchange,
            symbol=config.SYMBOL,
            type="market",
            side=close_side,
            amount=checked_size,
            intent="emergency_close",
            params={"reduceOnly": True},
            client_order_id_value=cid,
        )
        order_events.record("emergency_close_ack", client_order_id=resolved_cid, duplicate=duplicate, order=order_events.extract_order_summary(order))
    except Exception as e:
        order_events.record("emergency_close_error", client_order_id=cid, error=str(e))
        log.error(f"ACIL KAPATMA BAŞARISIZ: {e}")


def _amount_to_precision(exchange: ccxt.Exchange, size: float) -> float:
    """Binance lot size'a uydur."""
    try:
        return float(exchange.amount_to_precision(config.SYMBOL, size))
    except Exception:
        return round(size, 4)


def _reduce_only_market_amount(exchange: ccxt.Exchange, size: float, context: str) -> float | None:
    filter_result = xf.normalize_market_amount(exchange, config.SYMBOL, size)
    if not filter_result.ok:
        order_events.record(
            f"{context}_amount_filter_block",
            amount=size,
            reason=filter_result.reason,
        )
        return None
    return filter_result.amount or size


def _create_sl_order(
    exchange: ccxt.Exchange,
    sl_side: str,
    size: float,
    sl_price: float,
    ref_price: float | None = None,
    intent: str = "hard_sl",
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
    cid = client_order_id(config.SYMBOL, intent)
    order_events.record(
        "stop_order_submit",
        side=sl_side,
        amount=checked_size,
        stop_price=checked_sl_price,
        ref_price=ref_price,
        client_order_id=cid,
    )
    try:
        order, resolved_cid, duplicate = _create_order_idempotent(
            exchange,
            symbol=config.SYMBOL,
            type="stop_market",
            side=sl_side,
            amount=checked_size,
            intent=intent,
            params=eg.exchange_stop_params(checked_sl_price),
            client_order_id_value=cid,
        )
        order_events.record("stop_order_ack", client_order_id=resolved_cid, duplicate=duplicate, order=order_events.extract_order_summary(order))
        return order
    except ccxt.BaseError as e:
        order_events.record("stop_order_error", client_order_id=cid, side=sl_side, amount=checked_size, stop_price=checked_sl_price, error=str(e))
        log.error(f"SL emir hatası: {e}")
        return None


def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def _num_nonnegative(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out >= 0 else None


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
    cost = _num(order.get("cost")) or _num(order.get("cumQuote")) or _num(info.get("cumQuote"))
    if filled and cost:
        return cost / filled
    return fallback


def _order_filled_amount(order: dict | None, fallback: float) -> float:
    if not order:
        return fallback
    info = order.get("info") or {}
    for value in (order.get("filled"), order.get("executedQty"), info.get("executedQty")):
        parsed = _num_nonnegative(value)
        if parsed is not None:
            return parsed
    return fallback


def _order_requested_amount(order: dict | None, fallback: float) -> float:
    if not order:
        return fallback
    info = order.get("info") or {}
    return _num(order.get("amount")) or _num(order.get("origQty")) or _num(info.get("origQty")) or fallback


def _order_remaining_amount(order: dict | None, requested: float, filled: float) -> float:
    if not order:
        return max(requested - filled, 0.0)
    info = order.get("info") or {}
    for value in (order.get("remaining"), order.get("remainingQty"), info.get("remainingQty")):
        remaining = _num_nonnegative(value)
        if remaining is not None:
            return max(remaining, 0.0)
    return max(requested - filled, 0.0)


def _resolve_market_fill(
    exchange: ccxt.Exchange,
    order: dict | None,
    fallback_price: float,
    fallback_size: float,
    context: str = "market",
    position_side: str | None = None,
) -> FillResolution:
    price = _order_avg_price(order, fallback_price)
    size = _order_filled_amount(order, fallback_size)
    requested_size = _order_requested_amount(order, fallback_size)
    order_id = order.get("id") if order else None
    client_order_id_value = _client_order_id_from_order(order)
    resolved_order = order
    if order_id and (price == fallback_price or size == fallback_size):
        try:
            fetched = exchange.fetch_order(order_id, config.SYMBOL, signed_params())
            order_events.record(f"{context}_order_fetch", order=order_events.extract_order_summary(fetched))
            resolved_order = fetched
            price = _order_avg_price(fetched, price)
            size = _order_filled_amount(fetched, size)
            requested_size = _order_requested_amount(fetched, requested_size)
            client_order_id_value = client_order_id_value or _client_order_id_from_order(fetched)
        except Exception as e:
            order_events.record(f"{context}_order_fetch_error", order_id=order_id, error=str(e))
            log.warning(f"Market fill detayi cekilemedi, ilk order cevabi kullaniliyor: {e}")
    remaining_size = _order_remaining_amount(resolved_order, requested_size, size)
    partial = requested_size > 0 and (size + 1e-12 < requested_size or remaining_size > 1e-12)
    aborted = False
    if partial:
        policy = str(getattr(config, "PARTIAL_FILL_POLICY", "abort")).lower()
        if policy not in {"abort", "accept"}:
            policy = "abort"
        order_events.record(
            f"{context}_partial_fill_detected",
            order_id=order_id,
            client_order_id=client_order_id_value,
            requested_size=requested_size,
            filled_size=size,
            remaining_size=remaining_size,
            policy=policy,
        )
        if order_id and remaining_size > 0:
            _cancel_order_safe(exchange, order_id, client_order_id_value=client_order_id_value)
        if context == "entry" and policy == "abort":
            if position_side and size > 0:
                _safe_close_market(exchange, position_side, size)
            aborted = True
            order_events.record(
                "entry_partial_fill_aborted",
                order_id=order_id,
                client_order_id=client_order_id_value,
                closed_size=size,
            )
    order_events.record(
        f"{context}_fill_resolved",
        order_id=order_id,
        client_order_id=client_order_id_value,
        fallback_price=fallback_price,
        fallback_size=fallback_size,
        fill_price=price,
        filled_size=size,
        requested_size=requested_size,
        remaining_size=remaining_size,
        partial=partial,
        aborted=aborted,
    )
    return FillResolution(
        fill_price=price,
        filled_size=size,
        requested_size=requested_size,
        remaining_size=remaining_size,
        partial=partial,
        aborted=aborted,
        order_id=order_id,
        client_order_id=client_order_id_value,
        status=(resolved_order or {}).get("status") if resolved_order else None,
    )


def _cancel_order_safe(exchange: ccxt.Exchange, order_id: str, client_order_id_value: str | None = None):
    order_events.record("order_cancel_submit", order_id=order_id, client_order_id=client_order_id_value)
    try:
        exchange.cancel_order(order_id, config.SYMBOL, signed_params())
        order_events.record("order_cancel_ack", order_id=order_id, client_order_id=client_order_id_value)
    except Exception as e:
        order_events.record("order_cancel_error", order_id=order_id, client_order_id=client_order_id_value, error=str(e))
        log.warning(f"SL iptal hatası (zaten iptal/dolu olabilir): {e}")


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _order_id(order: dict) -> str | None:
    info = order.get("info") or {}
    oid = order.get("id") or info.get("orderId") or info.get("algoId")
    return str(oid) if oid is not None else None


def _order_side(order: dict) -> str:
    info = order.get("info") or {}
    return str(order.get("side") or info.get("side") or "").lower()


def _order_type(order: dict) -> str:
    info = order.get("info") or {}
    return str(order.get("type") or info.get("type") or info.get("origType") or "").lower()


def _is_reduce_only_stop_order(order: dict, side: str | None = None) -> bool:
    info = order.get("info") or {}
    if side and _order_side(order) != side.lower():
        return False
    if "stop" not in _order_type(order):
        return False
    return _truthy(order.get("reduceOnly")) or _truthy(info.get("reduceOnly"))


def _cleanup_extra_reduce_only_stops(exchange: ccxt.Exchange, keep_order_id: str | None, sl_side: str):
    if not keep_order_id:
        return
    try:
        open_orders = exchange.fetch_open_orders(config.SYMBOL, params=signed_params())
    except Exception as e:
        order_events.record("trailing_stop_cleanup_fetch_error", keep_order_id=keep_order_id, side=sl_side, error=str(e))
        log.warning(f"Trailing SL temizligi icin acik emirler cekilemedi: {e}")
        return

    keep_id = str(keep_order_id)
    stop_orders = [o for o in open_orders if _is_reduce_only_stop_order(o, sl_side)]
    extra_orders = [o for o in stop_orders if _order_id(o) and _order_id(o) != keep_id]
    if not extra_orders:
        return
    order_events.record(
        "trailing_stop_cleanup_detected",
        keep_order_id=keep_id,
        side=sl_side,
        active_stop_count=len(stop_orders),
        extra_stop_ids=[_order_id(o) for o in extra_orders],
    )
    for order in extra_orders:
        oid = _order_id(order)
        if oid:
            _cancel_order_safe(exchange, oid, client_order_id_value=_client_order_id_from_order(order))


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
    entry_client_order_id = client_order_id(config.SYMBOL, "entry")

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
        client_order_id=entry_client_order_id,
    )
    try:
        order, resolved_cid, duplicate = _create_order_idempotent(
            exchange,
            symbol=config.SYMBOL,
            type="market",
            side=order_side,
            amount=size,
            intent="entry",
            params={
                "reduceOnly": False,
                "newOrderRespType": getattr(config, "MARKET_ORDER_RESP_TYPE", "RESULT"),
            },
            client_order_id_value=entry_client_order_id,
        )
        order_events.record("entry_order_ack", client_order_id=resolved_cid, duplicate=duplicate, order=order_events.extract_order_summary(order))
        log.info(f"Pozisyon açıldı: {side.upper()} | miktar={size} | fiyat≈{price:.2f}")
    except ccxt.BaseError as e:
        order_events.record("entry_order_error", client_order_id=entry_client_order_id, side=order_side, amount=size, error=str(e))
        log.error(f"Pozisyon açma hatası: {e}")
        return None

    fill = _resolve_market_fill(exchange, order, price, size, context="entry", position_side=side)
    if fill.aborted:
        return None
    if fill.filled_size <= 0:
        order_events.record("entry_zero_fill_abort", client_order_id=fill.client_order_id, order_id=fill.order_id)
        log.error("Market entry emri fill olmadi, pozisyon acma iptal.")
        return None

    fill_price, filled_size = fill.fill_price, fill.filled_size
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

    sl_order = _create_sl_order(exchange, sl_side, filled_size, hard_sl, ref_price=fill_price, intent="hard_sl")
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
        "entry_client_order_id": fill.client_order_id or entry_client_order_id,
        "sl_client_order_id": _client_order_id_from_order(sl_order),
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
    new_sl_order = _create_sl_order(exchange, sl_side, size, hard_sl, ref_price=current_price, intent="trailing_sl")
    if new_sl_order is None:
        log.error("Yeni trailing SL oluşturulamadı, eski SL korunuyor.")
        return

    # Sonra eski emri iptal et
    if old_sl_id:
        _cancel_order_safe(exchange, old_sl_id)
    _cleanup_extra_reduce_only_stops(exchange, new_sl_order.get("id"), sl_side)

    position["sl"] = new_sl
    position["hard_sl"] = hard_sl
    position["sl_order_id"] = new_sl_order.get("id")
    log.info(f"Trailing soft SL guncellendi: {cur_sl:.2f} -> {new_sl:.2f} | hard={hard_sl:.2f}")


def close_position_market(exchange: ccxt.Exchange, side: str, size: float) -> bool:
    """Fail-safe reduce-only market close; cancel failures do not block close."""
    close_side = "sell" if side == "long" else "buy"
    try:
        exchange.cancel_all_orders(config.SYMBOL, signed_params())
        order_events.record("close_cancel_all_ack")
    except ccxt.BaseError as e:
        order_events.record("close_cancel_all_error", error=str(e))
        log.warning(f"Kapatma oncesi emir iptali basarisiz, market close yine denenecek: {e}")

    checked_size = _reduce_only_market_amount(exchange, size, "close")
    if checked_size is None:
        log.error("Kapatma miktari exchange filtrelerinden gecemedi.")
        return False

    cid = client_order_id(config.SYMBOL, "close")
    order_events.record("close_order_submit", side=close_side, amount=checked_size, requested_amount=size, reduce_only=True, client_order_id=cid)
    try:
        order, resolved_cid, duplicate = _create_order_idempotent(
            exchange,
            symbol=config.SYMBOL,
            type="market",
            side=close_side,
            amount=checked_size,
            intent="close",
            params={"reduceOnly": True},
            client_order_id_value=cid,
        )
        order_events.record("close_order_ack", client_order_id=resolved_cid, duplicate=duplicate, order=order_events.extract_order_summary(order))
        fill = _resolve_market_fill(exchange, order, 0.0, checked_size, context="close")
        fill_price, filled_size = fill.fill_price, fill.filled_size
        log.info(f"Pozisyon kapatildi (trend exit): {side.upper()} | miktar={filled_size} | fill={fill_price:.4f}")
        return filled_size > 0 and not fill.partial
    except ccxt.BaseError as e:
        order_events.record("close_order_error", client_order_id=cid, side=close_side, amount=size, error=str(e))
        log.error(f"Kapatma hatasi: {e}")
        return False


def close_all(exchange: ccxt.Exchange):
    try:
        exchange.cancel_all_orders(config.SYMBOL, signed_params())
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
        orders = exchange.fetch_open_orders(config.SYMBOL, params=signed_params())
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
