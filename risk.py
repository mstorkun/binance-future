import config


def position_size(balance: float, atr: float, price: float) -> float:
    """
    Risk tutarı (USDT) = bakiye × risk_pct
    Stop mesafesi (USDT/BTC) = ATR × çarpan
    Kontrat (BTC) = risk_usdt / stop_dist
    Kaldıraç margin'i etkiler, kontrat sayısını değil.
    """
    risk_usdt = balance * config.RISK_PER_TRADE_PCT
    stop_dist = atr * config.SL_ATR_MULT
    contracts = risk_usdt / stop_dist
    return round(contracts, 4)


def sl_tp_prices(entry: float, atr: float, side: str) -> tuple[float, float]:
    stop_dist = atr * config.SL_ATR_MULT
    tp_dist   = atr * config.TP_ATR_MULT

    if side == "long":
        sl = entry - stop_dist
        tp = entry + tp_dist
    else:
        sl = entry + stop_dist
        tp = entry - tp_dist

    return round(sl, 2), round(tp, 2)


def daily_loss_exceeded(start_balance: float, current_balance: float) -> bool:
    loss_pct = (start_balance - current_balance) / start_balance
    return loss_pct >= config.DAILY_LOSS_LIMIT_PCT
