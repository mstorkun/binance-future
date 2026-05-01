from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, InvalidOperation
from typing import Any

import config


@dataclass(frozen=True)
class FilterResult:
    ok: bool
    reason: str = ""
    amount: float | None = None
    price: float | None = None
    notional: float | None = None


@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    price_tick: Decimal | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    lot_step: Decimal | None = None
    min_qty: Decimal | None = None
    max_qty: Decimal | None = None
    market_lot_step: Decimal | None = None
    market_min_qty: Decimal | None = None
    market_max_qty: Decimal | None = None
    min_notional: Decimal | None = None
    pct_up: Decimal | None = None
    pct_down: Decimal | None = None


_CACHE: dict[tuple[int, str], tuple[SymbolFilters, float]] = {}


def clear_cache() -> None:
    _CACHE.clear()


def validate_entry_order(
    exchange: Any,
    symbol: str,
    side: str,
    amount: float,
    ref_price: float,
    *,
    order_type: str = "market",
) -> FilterResult:
    try:
        filters = get_symbol_filters(exchange, symbol)
    except Exception as exc:
        return FilterResult(False, f"exchange_filters_unavailable:{exc}")

    return validate_with_filters(
        filters,
        side=side,
        amount=amount,
        ref_price=ref_price,
        order_type=order_type,
    )


def validate_stop_order(
    exchange: Any,
    symbol: str,
    side: str,
    amount: float,
    stop_price: float,
    *,
    ref_price: float | None = None,
) -> FilterResult:
    try:
        filters = get_symbol_filters(exchange, symbol)
    except Exception as exc:
        return FilterResult(False, f"exchange_filters_unavailable:{exc}")

    return validate_with_filters(
        filters,
        side=side,
        amount=amount,
        price=stop_price,
        ref_price=ref_price,
        order_type="stop_market",
        allow_price_adjustment=True,
    )


def normalize_market_amount(exchange: Any, symbol: str, amount: float) -> FilterResult:
    try:
        filters = get_symbol_filters(exchange, symbol)
    except Exception as exc:
        return FilterResult(False, f"exchange_filters_unavailable:{exc}")

    amount_d = _to_decimal(amount)
    if amount_d is None or amount_d <= 0:
        return FilterResult(False, "bad_amount")

    step = filters.market_lot_step or filters.lot_step
    min_qty = filters.market_min_qty or filters.min_qty
    max_qty = filters.market_max_qty or filters.max_qty
    normalized_amount = _floor_to_step(amount_d, step)
    if normalized_amount is None or normalized_amount <= 0:
        return FilterResult(False, "amount_below_step")
    if min_qty is not None and normalized_amount < min_qty:
        return FilterResult(False, f"min_qty:{normalized_amount}<{min_qty}", float(normalized_amount))
    if max_qty is not None and normalized_amount > max_qty:
        return FilterResult(False, f"max_qty:{normalized_amount}>{max_qty}", float(normalized_amount))
    return FilterResult(True, "", float(normalized_amount))


def validate_with_filters(
    filters: SymbolFilters,
    *,
    side: str,
    amount: float,
    ref_price: float,
    order_type: str = "market",
    price: float | None = None,
    allow_price_adjustment: bool = False,
) -> FilterResult:
    amount_d = _to_decimal(amount)
    ref_d = _to_decimal(ref_price)
    if amount_d is None or amount_d <= 0:
        return FilterResult(False, "bad_amount")
    if ref_d is None or ref_d <= 0:
        return FilterResult(False, "bad_ref_price")

    step = filters.market_lot_step if order_type == "market" else filters.lot_step
    min_qty = filters.market_min_qty if order_type == "market" else filters.min_qty
    max_qty = filters.market_max_qty if order_type == "market" else filters.max_qty
    if step is None:
        step = filters.lot_step
    if min_qty is None:
        min_qty = filters.min_qty
    if max_qty is None:
        max_qty = filters.max_qty

    normalized_amount = _floor_to_step(amount_d, step)
    if normalized_amount is None or normalized_amount <= 0:
        return FilterResult(False, "amount_below_step")
    if min_qty is not None and normalized_amount < min_qty:
        return FilterResult(False, f"min_qty:{normalized_amount}<{min_qty}", float(normalized_amount))
    if max_qty is not None and normalized_amount > max_qty:
        return FilterResult(False, f"max_qty:{normalized_amount}>{max_qty}", float(normalized_amount))

    checked_price = ref_d
    output_price: Decimal | None = None
    if price is not None:
        price_d = _to_decimal(price)
        if price_d is None or price_d <= 0:
            return FilterResult(False, "bad_price", float(normalized_amount))
        normalized_price = _normalize_price(price_d, filters.price_tick, side, allow_price_adjustment)
        if normalized_price is None:
            return FilterResult(False, "price_below_tick", float(normalized_amount))
        if filters.min_price is not None and normalized_price < filters.min_price:
            return FilterResult(False, f"min_price:{normalized_price}<{filters.min_price}", float(normalized_amount), float(normalized_price))
        if filters.max_price is not None and normalized_price > filters.max_price:
            return FilterResult(False, f"max_price:{normalized_price}>{filters.max_price}", float(normalized_amount), float(normalized_price))
        checked_price = normalized_price
        output_price = normalized_price

    notional = normalized_amount * ref_d
    if filters.min_notional is not None and notional < filters.min_notional:
        return FilterResult(
            False,
            f"min_notional:{notional:.8f}<{filters.min_notional}",
            float(normalized_amount),
            float(output_price) if output_price is not None else None,
            float(notional),
        )

    pct_result = _validate_percent_price(filters, checked_price, ref_d)
    if pct_result is not None:
        return FilterResult(
            False,
            pct_result,
            float(normalized_amount),
            float(output_price) if output_price is not None else None,
            float(notional),
        )

    return FilterResult(
        True,
        "",
        float(normalized_amount),
        float(output_price) if output_price is not None else None,
        float(notional),
    )


def get_symbol_filters(exchange: Any, symbol: str) -> SymbolFilters:
    key = (id(exchange), _normalize_symbol(symbol))
    cached = _CACHE.get(key)
    now = time.monotonic()
    if cached is not None:
        filters, fetched_at = cached
        ttl = float(getattr(config, "EXCHANGE_FILTER_CACHE_TTL_SECONDS", 3600))
        if ttl > 0 and now - fetched_at <= ttl:
            return filters

    market = _fetch_exchange_info_symbol(exchange, symbol)
    filters = parse_symbol_filters(market)
    _CACHE[key] = (filters, now)
    return filters


def refresh_symbol_filters(exchange: Any, symbol: str) -> SymbolFilters:
    key = (id(exchange), _normalize_symbol(symbol))
    market = _fetch_exchange_info_symbol(exchange, symbol)
    filters = parse_symbol_filters(market)
    _CACHE[key] = (filters, time.monotonic())
    return filters


def parse_symbol_filters(market: dict[str, Any]) -> SymbolFilters:
    filter_map = {item.get("filterType"): item for item in market.get("filters", [])}
    price_filter = filter_map.get("PRICE_FILTER", {})
    lot_filter = filter_map.get("LOT_SIZE", {})
    market_lot_filter = filter_map.get("MARKET_LOT_SIZE", {})
    min_notional_filter = filter_map.get("MIN_NOTIONAL", {})
    percent_filter = filter_map.get("PERCENT_PRICE", {})

    return SymbolFilters(
        symbol=str(market.get("symbol") or ""),
        price_tick=_positive_decimal(price_filter.get("tickSize")),
        min_price=_positive_decimal(price_filter.get("minPrice")),
        max_price=_positive_decimal(price_filter.get("maxPrice")),
        lot_step=_positive_decimal(lot_filter.get("stepSize")),
        min_qty=_positive_decimal(lot_filter.get("minQty")),
        max_qty=_positive_decimal(lot_filter.get("maxQty")),
        market_lot_step=_positive_decimal(market_lot_filter.get("stepSize")),
        market_min_qty=_positive_decimal(market_lot_filter.get("minQty")),
        market_max_qty=_positive_decimal(market_lot_filter.get("maxQty")),
        min_notional=_positive_decimal(min_notional_filter.get("notional")),
        pct_up=_positive_decimal(percent_filter.get("multiplierUp")),
        pct_down=_positive_decimal(percent_filter.get("multiplierDown")),
    )


def _fetch_exchange_info_symbol(exchange: Any, symbol: str) -> dict[str, Any]:
    target = _normalize_symbol(symbol)
    info = None
    if hasattr(exchange, "fapiPublicGetExchangeInfo"):
        info = exchange.fapiPublicGetExchangeInfo()
    elif hasattr(exchange, "load_markets"):
        markets = exchange.load_markets()
        market = markets.get(symbol) or markets.get(target)
        if market and market.get("info"):
            return market["info"]

    if not info:
        raise RuntimeError("exchangeInfo method not available")

    for market in info.get("symbols", []):
        if _normalize_symbol(str(market.get("symbol") or "")) == target:
            status = str(market.get("status") or "").upper()
            if status and status != "TRADING":
                raise RuntimeError(f"symbol_not_trading:{status}")
            return market
    raise RuntimeError(f"symbol_not_found:{symbol}")


def _normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").split(":")[0].upper()


def _validate_percent_price(filters: SymbolFilters, price: Decimal, ref_price: Decimal) -> str | None:
    if filters.pct_up is not None:
        max_price = ref_price * filters.pct_up
        if price > max_price:
            return f"percent_price_high:{price}>{max_price}"
    if filters.pct_down is not None:
        min_price = ref_price * filters.pct_down
        if price < min_price:
            return f"percent_price_low:{price}<{min_price}"
    return None


def _normalize_price(
    price: Decimal,
    tick: Decimal | None,
    side: str,
    allow_adjustment: bool,
) -> Decimal | None:
    if tick is None:
        return price
    if tick <= 0:
        return None
    if price % tick == 0:
        return price
    if not allow_adjustment:
        return None
    rounding = ROUND_FLOOR if side.lower() == "sell" else ROUND_CEILING
    return (price / tick).to_integral_value(rounding=rounding) * tick


def _floor_to_step(value: Decimal, step: Decimal | None) -> Decimal | None:
    if step is None:
        return value
    if step <= 0:
        return None
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def _positive_decimal(value: Any) -> Decimal | None:
    out = _to_decimal(value)
    if out is None or out <= 0:
        return None
    return out


def _to_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
