from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

import config


PROD_PRIVATE_WS_BASE = "wss://fstream.binance.com/private/ws"
TESTNET_PRIVATE_WS_BASE = "wss://stream.binancefuture.com/ws"
LISTEN_KEY_TTL_MINUTES = 60
KEEPALIVE_EVERY_MINUTES = 30
RECONNECT_BEFORE_HOURS = 23


@dataclass(frozen=True)
class ListenKeyState:
    listen_key: str
    created_at: str
    keepalive_at: str
    expires_after_minutes: int = LISTEN_KEY_TTL_MINUTES

    def age_minutes(self, now: pd.Timestamp | None = None) -> float:
        return _age_minutes(self.created_at, now=now)

    def keepalive_age_minutes(self, now: pd.Timestamp | None = None) -> float:
        return _age_minutes(self.keepalive_at, now=now)

    def should_keepalive(self, now: pd.Timestamp | None = None) -> bool:
        return self.keepalive_age_minutes(now=now) >= KEEPALIVE_EVERY_MINUTES

    def should_reconnect(self, now: pd.Timestamp | None = None) -> bool:
        return self.age_minutes(now=now) >= RECONNECT_BEFORE_HOURS * 60


def start_listen_key(exchange: Any) -> ListenKeyState:
    response = exchange.fapiPrivatePostListenKey()
    listen_key = _extract_listen_key(response)
    now = _utc_now()
    return ListenKeyState(listen_key=listen_key, created_at=now, keepalive_at=now)


def keepalive_listen_key(exchange: Any, state: ListenKeyState) -> ListenKeyState:
    response = exchange.fapiPrivatePutListenKey({"listenKey": state.listen_key})
    listen_key = _extract_listen_key(response) or state.listen_key
    return ListenKeyState(
        listen_key=listen_key,
        created_at=state.created_at,
        keepalive_at=_utc_now(),
        expires_after_minutes=state.expires_after_minutes,
    )


def listen_key_ws_url(listen_key: str, *, testnet: bool | None = None) -> str:
    use_testnet = bool(getattr(config, "TESTNET", True)) if testnet is None else bool(testnet)
    base = TESTNET_PRIVATE_WS_BASE if use_testnet else PROD_PRIVATE_WS_BASE
    return f"{base}/{listen_key}"


def _extract_listen_key(response: Any) -> str:
    if isinstance(response, dict):
        return str(response.get("listenKey") or response.get("listenkey") or "")
    return ""


def _utc_now() -> str:
    return pd.Timestamp.now(tz="UTC").isoformat()


def _age_minutes(value: str, *, now: pd.Timestamp | None = None) -> float:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    current = now or pd.Timestamp.now(tz="UTC")
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    return (current - ts).total_seconds() / 60.0
