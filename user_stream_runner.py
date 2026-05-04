from __future__ import annotations

import argparse
import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Any

import config
import data
import order_events
import user_stream_client
import user_stream_events
import user_stream_runtime


class UserStreamEventGate:
    """Bounded duplicate and out-of-order guard for user stream events."""

    def __init__(self, max_seen: int = 10_000):
        self.max_seen = max(100, int(max_seen))
        self._seen_queue: deque[str] = deque()
        self._seen: set[str] = set()
        self._last_event_time: dict[str, int] = {}

    def accept(self, event: dict[str, Any]) -> tuple[bool, str]:
        identity = event_identity(event)
        if identity in self._seen:
            return False, "duplicate"
        order_key = order_event_key(event)
        event_time = event_time_ms(event)
        if order_key and event_time is not None:
            last = self._last_event_time.get(order_key)
            if last is not None and event_time < last:
                return False, "out_of_order"
            self._last_event_time[order_key] = event_time
        self._remember(identity)
        return True, "accepted"

    def _remember(self, identity: str) -> None:
        self._seen.add(identity)
        self._seen_queue.append(identity)
        while len(self._seen_queue) > self.max_seen:
            old = self._seen_queue.popleft()
            self._seen.discard(old)


def event_identity(event: dict[str, Any]) -> str:
    order = event.get("o") if isinstance(event.get("o"), dict) else {}
    parts = [
        str(event.get("e") or ""),
        str(event.get("E") or ""),
        str(event.get("T") or ""),
        str(order.get("s") or ""),
        str(order.get("i") or ""),
        str(order.get("c") or ""),
        str(order.get("x") or ""),
        str(order.get("X") or ""),
        str(order.get("z") or ""),
        str(order.get("t") or ""),
    ]
    return "|".join(parts)


def order_event_key(event: dict[str, Any]) -> str:
    order = event.get("o") if isinstance(event.get("o"), dict) else {}
    symbol = str(order.get("s") or "")
    order_id = str(order.get("i") or "")
    client_order_id = str(order.get("c") or "")
    if not symbol or (not order_id and not client_order_id):
        return ""
    return f"{symbol}|{order_id or client_order_id}"


def event_time_ms(event: dict[str, Any]) -> int | None:
    try:
        return int(event.get("E"))
    except (TypeError, ValueError):
        return None


def handle_message(
    message: str | bytes,
    *,
    gate: UserStreamEventGate | None = None,
    state_path: str | Path | None = None,
) -> dict[str, Any]:
    if isinstance(message, bytes):
        message = message.decode("utf-8")
    event = json.loads(message)
    gate = gate or UserStreamEventGate()
    accepted, reason = gate.accept(event)
    if not accepted:
        return {"action": "skip", "reason": reason}
    if user_stream_events.is_order_trade_update(event):
        result = user_stream_runtime.handle_order_trade_update(event, state_path=state_path)
        return {
            "action": "order_update",
            "decision": result["decision"],
            "changed": result["changed"],
        }
    return {"action": "ignore", "event_type": event.get("e")}


async def run_user_stream(
    exchange: Any,
    *,
    state_path: str | Path | None = None,
    max_messages: int | None = None,
    stop_after_seconds: float | None = None,
) -> int:
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError("websockets dependency is missing; run pip install -r requirements.txt") from exc

    state = user_stream_client.start_listen_key(exchange)
    gate = UserStreamEventGate()
    processed = 0
    started = asyncio.get_running_loop().time()
    reconnect_delay = 1.0

    while True:
        if stop_after_seconds is not None and asyncio.get_running_loop().time() - started >= stop_after_seconds:
            return processed
        if state.should_reconnect():
            state = user_stream_client.start_listen_key(exchange)
        url = user_stream_client.listen_key_ws_url(state.listen_key)
        try:
            async with websockets.connect(url, ping_interval=180, ping_timeout=30) as ws:
                reconnect_delay = 1.0
                while True:
                    if max_messages is not None and processed >= max_messages:
                        return processed
                    if stop_after_seconds is not None and asyncio.get_running_loop().time() - started >= stop_after_seconds:
                        return processed
                    if state.should_keepalive():
                        state = user_stream_client.keepalive_listen_key(exchange, state)
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    handle_message(message, gate=gate, state_path=state_path)
                    processed += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not isinstance(exc, OSError) and not exc.__class__.__module__.startswith("websockets"):
                raise
            order_events.record(
                "user_stream_connection_error",
                error=exc.__class__.__name__,
                detail=str(exc),
                processed=processed,
            )
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2.0, 30.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Binance USD-M Futures user-data stream consumer.")
    parser.add_argument("--dry-run", action="store_true", help="Create listenKey and print URL without opening websocket.")
    parser.add_argument("--max-messages", type=int, default=0)
    parser.add_argument("--stop-after-seconds", type=float, default=0.0)
    parser.add_argument("--state-path", default="")
    args = parser.parse_args()

    exchange = data.make_exchange()
    if args.dry_run:
        state = user_stream_client.start_listen_key(exchange)
        print(json.dumps({
            "listen_key": state.listen_key,
            "url": user_stream_client.listen_key_ws_url(state.listen_key),
            "keepalive_every_minutes": user_stream_client.KEEPALIVE_EVERY_MINUTES,
            "reconnect_before_hours": user_stream_client.RECONNECT_BEFORE_HOURS,
        }, indent=2, sort_keys=True))
        return 0

    processed = asyncio.run(run_user_stream(
        exchange,
        state_path=args.state_path or None,
        max_messages=args.max_messages or None,
        stop_after_seconds=args.stop_after_seconds or None,
    ))
    print(json.dumps({"processed": processed}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
