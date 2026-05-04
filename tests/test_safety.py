import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

import ccxt
import pandas as pd

import account_safety
import alerts
import config
import bias_audit
import bias_audit_report
import correlation_stress
import data
import decision_snapshots
import emergency_kill_switch
import execution_guard
import exit_ladder
import exchange_filters
import flow_data
import carry_research
import go_live_preflight
import live_state
import order_manager
import order_events
import paper_runtime
import paper_decision_report
import pair_universe
import pattern_ablation
import paper_runner
import paper_report
import ops_status
import portfolio_candidate_sweep
import portfolio_cost_stress
import portfolio_holdout
import portfolio_param_walk_forward
import pbo_report
import protections
import risk
import risk_adjusted_report
import risk_management
import risk_metrics
import runtime_guards
import timeframe_sweep
import trade_executor
import twap_execution
import user_stream_client
import user_stream_events
import user_stream_reconcile
import user_stream_runtime
import user_stream_runner
import walk_forward


class FakeExchange:
    def __init__(self):
        self.created_orders = []
        self.cancel_all_params = []

    def fapiPublicGetExchangeInfo(self):
        return {
            "symbols": [
                _fake_symbol_info("DOGEUSDT", price_tick="0.00010", step="1", min_qty="1"),
                _fake_symbol_info("SOLUSDT", price_tick="0.01000", step="0.01", min_qty="0.01"),
            ]
        }

    def cancel_all_orders(self, symbol, params=None):
        self.cancel_all_params.append(params or {})
        raise ccxt.ExchangeError("cancel failed")

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": amount,
            "average": 100.0,
            "params": params or {},
        }
        self.created_orders.append(order)
        return order


def _fake_symbol_info(symbol, *, price_tick="0.00010", step="1", min_qty="1"):
    return {
        "symbol": symbol,
        "status": "TRADING",
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.00001",
                "maxPrice": "1000",
                "tickSize": price_tick,
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": min_qty,
                "maxQty": "10000000",
                "stepSize": step,
            },
            {
                "filterType": "MARKET_LOT_SIZE",
                "minQty": min_qty,
                "maxQty": "10000000",
                "stepSize": step,
            },
            {"filterType": "MIN_NOTIONAL", "notional": "5"},
            {
                "filterType": "PERCENT_PRICE",
                "multiplierUp": "1.1500",
                "multiplierDown": "0.8500",
            },
        ],
    }


class FakeExchangeInfo:
    def fapiPublicGetExchangeInfo(self):
        return {
            "symbols": [
                _fake_symbol_info("DOGEUSDT", price_tick="0.00010", step="1", min_qty="1")
            ]
        }


class CountingExchangeInfo(FakeExchangeInfo):
    def __init__(self):
        self.calls = 0

    def fapiPublicGetExchangeInfo(self):
        self.calls += 1
        return super().fapiPublicGetExchangeInfo()


class RetryCreateExchange:
    def __init__(self):
        self.created_params = []

    def create_order(self, symbol, type, side, amount, params=None):
        self.created_params.append(params or {})
        if len(self.created_params) == 1:
            raise ccxt.NetworkError("timeout after submit")
        return {
            "id": "retry-order",
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "amount": amount,
            "filled": amount,
            "average": 100.0,
        }


class DuplicateCreateExchange:
    def __init__(self):
        self.fetch_params = None
        self.raw_params = None

    def create_order(self, symbol, type, side, amount, params=None):
        raise ccxt.ExchangeError("Duplicate client order id")

    def fapiPrivateGetOrder(self, params):
        self.raw_params = params or {}
        return {
            "orderId": "existing-order",
            "clientOrderId": self.raw_params.get("origClientOrderId"),
            "origQty": "2.0",
            "executedQty": "2.0",
            "avgPrice": "101.0",
            "status": "FILLED",
        }

    def fetch_order(self, order_id, symbol, params=None):
        self.fetch_params = params or {}
        return {
            "id": "fallback-existing-order",
            "clientOrderId": self.fetch_params.get("origClientOrderId"),
            "amount": 2.0,
            "filled": 2.0,
            "average": 101.0,
        }


class FetchFallbackExchange:
    def __init__(self):
        self.fetch_order_id = "unset"
        self.fetch_symbol = None
        self.fetch_params = None

    def fetch_order(self, order_id, symbol, params=None):
        self.fetch_order_id = order_id
        self.fetch_symbol = symbol
        self.fetch_params = params or {}
        return {
            "id": "fallback-existing-order",
            "clientOrderId": self.fetch_params.get("origClientOrderId"),
            "amount": 1.0,
            "filled": 1.0,
            "average": 100.0,
        }


class RejectCodeExchange:
    def __init__(self, message):
        self.message = message
        self.fetch_called = False

    def create_order(self, symbol, type, side, amount, params=None):
        raise ccxt.ExchangeError(self.message)

    def fetch_order(self, order_id, symbol, params=None):
        self.fetch_called = True
        return {}


class PartialFillExchange(FakeExchangeInfo):
    def __init__(self):
        self.cancelled = []
        self.created_orders = []

    def cancel_order(self, order_id, symbol, params=None):
        self.cancelled.append({"order_id": order_id, "symbol": symbol, "params": params or {}})

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "id": f"created-{len(self.created_orders) + 1}",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": amount,
            "average": 100.0,
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "params": params or {},
        }
        self.created_orders.append(order)
        return order


class StopOrderExchange(FakeExchangeInfo):
    def __init__(self):
        self.created_orders = []

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "id": "stop-order",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": 0.0,
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "params": params or {},
        }
        self.created_orders.append(order)
        return order


class PartialCloseExchange(FakeExchangeInfo):
    def __init__(self):
        self.created_orders = []
        self.cancel_all_calls = []

    def cancel_all_orders(self, symbol, params=None):
        self.cancel_all_calls.append({"symbol": symbol, "params": params or {}})

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "id": "partial-close",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": amount / 2.0,
            "remaining": amount / 2.0,
            "average": 0.5,
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "params": params or {},
        }
        self.created_orders.append(order)
        return order


class TrailingCleanupExchange(FakeExchangeInfo):
    def __init__(self):
        self.created_orders = []
        self.open_orders = [
            {"id": "old-stop", "type": "stop_market", "side": "sell", "reduceOnly": True, "clientOrderId": "old-cid"},
            {"id": "stale-stop", "type": "stop_market", "side": "sell", "reduceOnly": True, "clientOrderId": "stale-cid"},
            {"id": "buy-stop", "type": "stop_market", "side": "buy", "reduceOnly": True},
        ]
        self.cancelled = []

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "id": "new-stop",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": 0.0,
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "reduceOnly": True,
            "params": params or {},
        }
        self.created_orders.append(order)
        self.open_orders.append(order)
        return order

    def cancel_order(self, order_id, symbol, params=None):
        self.cancelled.append(order_id)
        if order_id == "old-stop" and self.cancelled.count(order_id) == 1:
            raise ccxt.ExchangeError("first cancel failed")
        self.open_orders = [o for o in self.open_orders if o["id"] != order_id]

    def fetch_open_orders(self, symbol, params=None):
        return list(self.open_orders)


class KillSwitchExchange(FakeExchangeInfo):
    def __init__(self):
        self.open_orders = {
            "DOGE/USDT": [
                {"id": "stop-1", "type": "stop_market", "side": "sell", "amount": 10, "reduceOnly": True}
            ]
        }
        self.positions = [
            {
                "symbol": "DOGE/USDT",
                "contracts": 12.7,
                "side": "long",
                "entryPrice": 0.5,
                "info": {"symbol": "DOGEUSDT", "positionAmt": "12.7"},
            }
        ]
        self.cancelled = []
        self.created_orders = []

    def fetch_open_orders(self, symbol, params=None):
        return list(self.open_orders.get(symbol, []))

    def fetch_positions(self, symbols):
        return [pos for pos in self.positions if pos["symbol"] in symbols]

    def cancel_order(self, order_id, symbol, params=None):
        self.cancelled.append({"order_id": order_id, "symbol": symbol, "params": params or {}})

    def create_order(self, symbol, type, side, amount, params=None):
        order = {
            "id": f"close-{len(self.created_orders) + 1}",
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "filled": amount,
            "average": 0.5,
            "clientOrderId": (params or {}).get("newClientOrderId"),
            "params": params or {},
        }
        self.created_orders.append(order)
        return order


class FakeAccountExchange:
    def __init__(self, dual_side=False, leverage=10, margin_mode="cross", contracts=0, has_stop=True):
        self.dual_side = dual_side
        self.leverage = leverage
        self.margin_mode = margin_mode
        self.contracts = contracts
        self.has_stop = has_stop

    def fapiPrivateGetPositionSideDual(self):
        return {"dualSidePosition": self.dual_side}

    def fetch_positions(self, symbols):
        return [
            {
                "symbol": symbol,
                "contracts": self.contracts,
                "marginMode": self.margin_mode,
                "info": {
                    "symbol": symbol.replace("/", ""),
                    "leverage": str(self.leverage),
                    "marginType": self.margin_mode,
                    "positionAmt": str(self.contracts),
                },
                "leverage": self.leverage,
            }
            for symbol in symbols
        ]

    def set_leverage(self, leverage, symbol, params=None):
        return {"symbol": symbol.replace("/", ""), "leverage": leverage}

    def set_margin_mode(self, margin_mode, symbol, params=None):
        return {"symbol": symbol.replace("/", ""), "marginMode": margin_mode}

    def fetch_open_orders(self, symbol):
        if not self.has_stop:
            return []
        return [{"id": "stop-1", "type": "stop_market", "reduceOnly": True}]


class FakeListenKeyExchange:
    def __init__(self):
        self.post_calls = 0
        self.put_calls = []

    def fapiPrivatePostListenKey(self):
        self.post_calls += 1
        return {"listenKey": "listen-key-1"}

    def fapiPrivatePutListenKey(self, params):
        self.put_calls.append(params)
        return {"listenKey": params["listenKey"]}


class SafetyTests(unittest.TestCase):
    def test_live_state_persists_positions_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_state.json"
            positions = live_state.upsert_position(
                "DOGE/USDT",
                {"side": "long", "entry": 0.1, "size": 100, "extreme": 0.12},
                path,
            )
            self.assertIn("DOGE/USDT", positions)
            loaded = live_state.load_positions(path)
            self.assertEqual(loaded["DOGE/USDT"]["side"], "long")
            self.assertEqual(loaded["DOGE/USDT"]["extreme"], 0.12)

            positions = live_state.remove_position("DOGE/USDT", path)
            self.assertNotIn("DOGE/USDT", positions)
            self.assertEqual(live_state.load_positions(path), {})
            self.assertTrue((Path(tmp) / "live_state.json.bak1").exists())

    def test_live_state_uses_backup_after_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_state.json"
            live_state.save_positions({"DOGE/USDT": {"side": "long", "size": 10}}, path)
            live_state.save_positions({"LINK/USDT": {"side": "short", "size": 5}}, path)
            path.write_text("{bad json", encoding="utf-8")
            loaded = live_state.load_positions(path)
            self.assertEqual(set(loaded), {"DOGE/USDT"})

    def test_live_state_uses_backup_when_primary_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live_state.json"
            live_state.save_positions({"DOGE/USDT": {"side": "long", "size": 10}}, path)
            live_state.save_positions({"LINK/USDT": {"side": "short", "size": 5}}, path)
            path.unlink()
            loaded = live_state.load_positions(path)
            self.assertEqual(set(loaded), {"DOGE/USDT"})

    def test_live_state_fails_closed_when_corrupt_without_backup(self):
        old_fail = getattr(config, "LIVE_STATE_FAIL_CLOSED", True)
        try:
            config.LIVE_STATE_FAIL_CLOSED = True
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "live_state.json"
                path.write_text("{bad json", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "Live state corrupted"):
                    live_state.load_state(path)
        finally:
            config.LIVE_STATE_FAIL_CLOSED = old_fail

    def test_live_state_reconcile_drops_closed_local_positions(self):
        local = {
            "DOGE/USDT": {"side": "long"},
            "LINK/USDT": {"side": "short"},
            "OLD/USDT": {"side": "long"},
        }
        exchange_positions = [
            {"symbol": "DOGE/USDT", "contracts": 10},
            {"symbol": "LINK/USDT", "contracts": 0},
        ]
        reconciled, removed = live_state.reconcile_positions(
            local,
            exchange_positions,
            ["DOGE/USDT", "LINK/USDT"],
        )
        self.assertEqual(set(reconciled), {"DOGE/USDT"})
        self.assertEqual(removed, ["LINK/USDT", "OLD/USDT"])

    def test_signed_params_include_recv_window(self):
        old_recv = getattr(config, "RECV_WINDOW_MS", 5000)
        try:
            config.RECV_WINDOW_MS = 7000
            params = order_manager.signed_params({"reduceOnly": True})
            self.assertEqual(params["recvWindow"], 7000)
            self.assertTrue(params["reduceOnly"])
        finally:
            config.RECV_WINDOW_MS = old_recv

    def test_make_exchange_enables_time_difference_adjustment(self):
        exchange = data.make_exchange()
        self.assertEqual(exchange.options.get("defaultType"), "future")
        self.assertTrue(exchange.options.get("adjustForTimeDifference"))
        self.assertEqual(exchange.options.get("recvWindow"), config.RECV_WINDOW_MS)

    def test_live_profile_guard_blocks_research_profile_live_exchange(self):
        old_values = {
            "TESTNET": config.TESTNET,
            "LIVE_TRADING_APPROVED": config.LIVE_TRADING_APPROVED,
            "LEVERAGE": config.LEVERAGE,
            "RISK_PER_TRADE_PCT": config.RISK_PER_TRADE_PCT,
            "DAILY_LOSS_LIMIT_PCT": config.DAILY_LOSS_LIMIT_PCT,
        }
        try:
            config.TESTNET = False
            config.LIVE_TRADING_APPROVED = True
            config.LEVERAGE = 10
            config.RISK_PER_TRADE_PCT = 0.04
            config.DAILY_LOSS_LIMIT_PCT = 0.06
            with self.assertRaisesRegex(RuntimeError, "profile guard"):
                data.make_exchange()
        finally:
            for key, value in old_values.items():
                setattr(config, key, value)

    def test_live_profile_status_accepts_balanced_profile(self):
        keys = [
            "LEVERAGE",
            "RISK_PER_TRADE_PCT",
            "DAILY_LOSS_LIMIT_PCT",
            "MAX_OPEN_POSITIONS",
            "MARGIN_MODE",
            "LIQUIDATION_GUARD_ENABLED",
            "PROTECTIONS_ENABLED",
        ]
        old_values = {key: getattr(config, key) for key in keys}
        try:
            config.LEVERAGE = 5
            config.RISK_PER_TRADE_PCT = 0.03
            config.DAILY_LOSS_LIMIT_PCT = 0.03
            config.MAX_OPEN_POSITIONS = 2
            config.MARGIN_MODE = "cross"
            config.LIQUIDATION_GUARD_ENABLED = True
            config.PROTECTIONS_ENABLED = True
            status = data.live_profile_status()
            self.assertTrue(status["ok"])
            self.assertEqual(status["required_live_profile"], "balanced_live_v1")
            self.assertEqual(status["mismatches"], [])
        finally:
            for key, value in old_values.items():
                setattr(config, key, value)

    def test_user_data_stream_gate_blocks_balanced_live_exchange_until_ready(self):
        keys = [
            "TESTNET",
            "LIVE_TRADING_APPROVED",
            "LEVERAGE",
            "RISK_PER_TRADE_PCT",
            "DAILY_LOSS_LIMIT_PCT",
            "MAX_OPEN_POSITIONS",
            "MARGIN_MODE",
            "LIQUIDATION_GUARD_ENABLED",
            "PROTECTIONS_ENABLED",
            "USER_DATA_STREAM_REQUIRED_FOR_LIVE",
            "USER_DATA_STREAM_READY",
        ]
        old_values = {key: getattr(config, key) for key in keys}
        try:
            config.TESTNET = False
            config.LIVE_TRADING_APPROVED = True
            config.LEVERAGE = 5
            config.RISK_PER_TRADE_PCT = 0.03
            config.DAILY_LOSS_LIMIT_PCT = 0.03
            config.MAX_OPEN_POSITIONS = 2
            config.MARGIN_MODE = "cross"
            config.LIQUIDATION_GUARD_ENABLED = True
            config.PROTECTIONS_ENABLED = True
            config.USER_DATA_STREAM_REQUIRED_FOR_LIVE = True
            config.USER_DATA_STREAM_READY = False
            with self.assertRaisesRegex(RuntimeError, "user-data stream gate"):
                data.make_exchange()
        finally:
            for key, value in old_values.items():
                setattr(config, key, value)

    def test_user_data_stream_status_passes_when_not_required(self):
        old_required = config.USER_DATA_STREAM_REQUIRED_FOR_LIVE
        old_ready = config.USER_DATA_STREAM_READY
        try:
            config.USER_DATA_STREAM_REQUIRED_FOR_LIVE = False
            config.USER_DATA_STREAM_READY = False
            status = data.user_data_stream_status()
            self.assertTrue(status["ok"])
            self.assertFalse(status["required_for_live"])
        finally:
            config.USER_DATA_STREAM_REQUIRED_FOR_LIVE = old_required
            config.USER_DATA_STREAM_READY = old_ready

    def test_live_profile_status_requires_safety_flags(self):
        old_values = {
            "LEVERAGE": config.LEVERAGE,
            "RISK_PER_TRADE_PCT": config.RISK_PER_TRADE_PCT,
            "DAILY_LOSS_LIMIT_PCT": config.DAILY_LOSS_LIMIT_PCT,
            "MAX_OPEN_POSITIONS": config.MAX_OPEN_POSITIONS,
            "MARGIN_MODE": config.MARGIN_MODE,
            "LIQUIDATION_GUARD_ENABLED": config.LIQUIDATION_GUARD_ENABLED,
            "PROTECTIONS_ENABLED": config.PROTECTIONS_ENABLED,
        }
        try:
            config.LEVERAGE = 5
            config.RISK_PER_TRADE_PCT = 0.03
            config.DAILY_LOSS_LIMIT_PCT = 0.03
            config.MAX_OPEN_POSITIONS = 2
            config.MARGIN_MODE = "cross"
            config.LIQUIDATION_GUARD_ENABLED = False
            config.PROTECTIONS_ENABLED = False
            status = data.live_profile_status()
            self.assertFalse(status["ok"])
            self.assertIn("LIQUIDATION_GUARD_ENABLED", {row["key"] for row in status["mismatches"]})
            self.assertIn("PROTECTIONS_ENABLED", {row["key"] for row in status["mismatches"]})
        finally:
            for key, value in old_values.items():
                setattr(config, key, value)

    def test_runtime_trading_disabled_flag_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trading_disabled.flag"
            self.assertFalse(runtime_guards.trading_disabled(path))
            runtime_guards.disable_trading("unit test", path)
            self.assertTrue(runtime_guards.trading_disabled(path))
            with self.assertRaisesRegex(RuntimeError, "Trading is disabled"):
                runtime_guards.assert_trading_enabled(path)
            runtime_guards.enable_trading(path)
            self.assertFalse(runtime_guards.trading_disabled(path))

    def test_go_live_preflight_fails_closed_by_default(self):
        report = go_live_preflight.build_preflight(include_files=False)
        self.assertFalse(report["ok"])
        failed = {row["name"] for row in report["checks"] if not row["ok"]}
        self.assertIn("testnet_disabled_for_live", failed)
        self.assertIn("live_approved", failed)
        self.assertIn("live_profile", failed)
        self.assertIn("user_data_stream", failed)

    def test_user_stream_order_trade_update_parser_flags_reduce_only_fill(self):
        event = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1568879465651,
            "T": 1568879465650,
            "o": {
                "s": "DOGEUSDT",
                "c": "DOGE_1770000000000_hard_sl_abc12345",
                "S": "SELL",
                "o": "STOP_MARKET",
                "ot": "STOP_MARKET",
                "q": "100",
                "ap": "0.25",
                "sp": "0.24",
                "x": "TRADE",
                "X": "FILLED",
                "i": 8886774,
                "l": "100",
                "z": "100",
                "L": "0.24",
                "N": "USDT",
                "n": "0.01",
                "T": 1568879465650,
                "t": 123,
                "R": True,
                "ps": "BOTH",
                "rp": "-2.5",
                "pP": True,
                "er": "0",
            },
        }
        update = user_stream_events.parse_order_trade_update(event)
        self.assertEqual(update.symbol, "DOGE/USDT")
        self.assertEqual(update.status, "FILLED")
        self.assertTrue(update.terminal)
        self.assertTrue(update.reduce_only)
        self.assertTrue(update.requires_immediate_reconcile)
        self.assertAlmostEqual(update.accumulated_filled_qty, 100.0)
        self.assertAlmostEqual(update.realized_profit, -2.5)

    def test_user_stream_order_trade_update_records_jsonl(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                update = user_stream_events.record_order_trade_update({
                    "e": "ORDER_TRADE_UPDATE",
                    "E": 1,
                    "T": 2,
                    "o": {
                        "s": "TRXUSDT",
                        "c": "adl_autoclose",
                        "S": "SELL",
                        "o": "LIQUIDATION",
                        "x": "CALCULATED",
                        "X": "NEW",
                        "i": 1,
                        "q": "1",
                        "z": "0",
                        "R": False,
                    },
                })
                self.assertTrue(update.liquidation_or_adl)
                rows = [
                    json.loads(line)
                    for line in Path(config.ORDER_EVENTS_JSONL).read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(rows[0]["event_type"], "user_stream_order_update")
                self.assertEqual(rows[0]["symbol"], "TRX/USDT")
                self.assertTrue(rows[0]["liquidation_or_adl"])
                self.assertTrue(rows[0]["requires_immediate_reconcile"])
        finally:
            config.ORDER_EVENTS_JSONL = old_path

    def test_user_stream_listen_key_lifecycle_helpers(self):
        exchange = FakeListenKeyExchange()
        state = user_stream_client.start_listen_key(exchange)
        self.assertEqual(state.listen_key, "listen-key-1")
        self.assertEqual(exchange.post_calls, 1)
        refreshed = user_stream_client.keepalive_listen_key(exchange, state)
        self.assertEqual(refreshed.listen_key, "listen-key-1")
        self.assertEqual(exchange.put_calls, [{"listenKey": "listen-key-1"}])
        self.assertTrue(user_stream_client.listen_key_ws_url("abc", testnet=False).endswith("/private/ws/abc"))
        self.assertTrue(user_stream_client.listen_key_ws_url("abc", testnet=True).endswith("/ws/abc"))

    def test_user_stream_listen_key_state_refresh_decisions(self):
        created = pd.Timestamp("2026-01-01T00:00:00Z")
        state = user_stream_client.ListenKeyState(
            listen_key="abc",
            created_at=created.isoformat(),
            keepalive_at=created.isoformat(),
        )
        self.assertFalse(state.should_keepalive(now=created + pd.Timedelta(minutes=29)))
        self.assertTrue(state.should_keepalive(now=created + pd.Timedelta(minutes=30)))
        self.assertFalse(state.should_reconnect(now=created + pd.Timedelta(hours=22)))
        self.assertTrue(state.should_reconnect(now=created + pd.Timedelta(hours=23)))

    def test_user_stream_reconcile_removes_reduce_only_filled_position(self):
        update = user_stream_events.parse_order_trade_update({
            "e": "ORDER_TRADE_UPDATE",
            "E": 1,
            "T": 2,
            "o": {
                "s": "DOGEUSDT",
                "c": "hard-sl",
                "S": "SELL",
                "o": "STOP_MARKET",
                "ot": "STOP_MARKET",
                "x": "TRADE",
                "X": "FILLED",
                "i": 1,
                "q": "100",
                "z": "100",
                "R": True,
            },
        })
        positions, decision = user_stream_reconcile.apply_order_update_to_positions(
            {"DOGE/USDT": {"side": "long", "size": 100}},
            update,
        )
        self.assertNotIn("DOGE/USDT", positions)
        self.assertEqual(decision["action"], "remove_position")

    def test_user_stream_reconcile_marks_partial_entry_without_removing(self):
        update = user_stream_events.parse_order_trade_update({
            "e": "ORDER_TRADE_UPDATE",
            "E": 1,
            "T": 2,
            "o": {
                "s": "LINKUSDT",
                "c": "entry",
                "S": "BUY",
                "o": "MARKET",
                "x": "TRADE",
                "X": "PARTIALLY_FILLED",
                "i": 2,
                "q": "10",
                "z": "4",
                "R": False,
            },
        })
        positions, decision = user_stream_reconcile.apply_order_update_to_positions(
            {"LINK/USDT": {"side": "long", "size": 10}},
            update,
        )
        self.assertIn("LINK/USDT", positions)
        self.assertEqual(decision["action"], "mark_position")
        self.assertEqual(positions["LINK/USDT"]["last_user_stream_order_status"], "PARTIALLY_FILLED")
        self.assertEqual(positions["LINK/USDT"]["last_user_stream_filled_qty"], 4.0)

    def test_user_stream_runtime_persists_reconciled_positions(self):
        old_events = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                state_path = Path(tmp) / "live_state.json"
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "order_events.jsonl")
                live_state.save_positions({"DOGE/USDT": {"side": "long", "size": 100}}, state_path)
                result = user_stream_runtime.handle_order_trade_update(
                    {
                        "e": "ORDER_TRADE_UPDATE",
                        "E": 1,
                        "T": 2,
                        "o": {
                            "s": "DOGEUSDT",
                            "c": "hard-sl",
                            "S": "SELL",
                            "o": "STOP_MARKET",
                            "ot": "STOP_MARKET",
                            "x": "TRADE",
                            "X": "FILLED",
                            "i": 1,
                            "q": "100",
                            "z": "100",
                            "R": True,
                        },
                    },
                    state_path=state_path,
                )
                self.assertTrue(result["changed"])
                self.assertEqual(live_state.load_positions(state_path), {})
                rows = [
                    json.loads(line)
                    for line in Path(config.ORDER_EVENTS_JSONL).read_text(encoding="utf-8").splitlines()
                ]
                self.assertEqual(rows[0]["event_type"], "user_stream_order_update")
                self.assertEqual(rows[1]["event_type"], "user_stream_reconcile_decision")
                self.assertEqual(rows[1]["action"], "remove_position")
        finally:
            config.ORDER_EVENTS_JSONL = old_events

    def test_user_stream_runner_gate_rejects_duplicate_and_out_of_order_events(self):
        gate = user_stream_runner.UserStreamEventGate()
        event = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 10,
            "o": {"s": "DOGEUSDT", "i": 1, "c": "cid", "x": "NEW", "X": "NEW", "z": "0"},
        }
        self.assertEqual(gate.accept(event), (True, "accepted"))
        self.assertEqual(gate.accept(event), (False, "duplicate"))
        older = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 9,
            "o": {"s": "DOGEUSDT", "i": 1, "c": "cid", "x": "TRADE", "X": "PARTIALLY_FILLED", "z": "1"},
        }
        self.assertEqual(gate.accept(older), (False, "out_of_order"))

    def test_user_stream_runner_handle_message_reconciles_state(self):
        old_events = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                state_path = Path(tmp) / "live_state.json"
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                live_state.save_positions({"DOGE/USDT": {"side": "long", "size": 100}}, state_path)
                result = user_stream_runner.handle_message(json.dumps({
                    "e": "ORDER_TRADE_UPDATE",
                    "E": 10,
                    "T": 11,
                    "o": {
                        "s": "DOGEUSDT",
                        "i": 1,
                        "c": "hard-sl",
                        "S": "SELL",
                        "o": "STOP_MARKET",
                        "ot": "STOP_MARKET",
                        "x": "TRADE",
                        "X": "FILLED",
                        "q": "100",
                        "z": "100",
                        "R": True,
                    },
                }), state_path=state_path)
                self.assertEqual(result["action"], "order_update")
                self.assertTrue(result["changed"])
                self.assertEqual(live_state.load_positions(state_path), {})
        finally:
            config.ORDER_EVENTS_JSONL = old_events

    def test_account_safety_confirms_one_way_and_leverage(self):
        old_leverage = config.LEVERAGE
        try:
            config.LEVERAGE = 10
            status = account_safety.account_safety_status(
                FakeAccountExchange(dual_side=False, leverage=10),
                ["DOGE/USDT", "LINK/USDT"],
            )
            self.assertTrue(status["ok"])
            self.assertEqual(status["position_mode"]["mode"], "one_way")
            self.assertTrue(all(row["ok"] for row in status["leverage"]["symbols"]))
            self.assertTrue(status["margin_mode"]["ok"])
            self.assertTrue(status["hard_stop"]["ok"])
        finally:
            config.LEVERAGE = old_leverage

    def test_account_safety_blocks_hedge_mode(self):
        status = account_safety.account_safety_status(
            FakeAccountExchange(dual_side=True, leverage=config.LEVERAGE),
            ["DOGE/USDT"],
        )
        self.assertFalse(status["ok"])
        self.assertEqual(status["position_mode"]["reason"], "hedge_mode_enabled")

    def test_account_safety_reports_margin_mode_mismatch(self):
        status = account_safety.account_safety_status(
            FakeAccountExchange(dual_side=False, leverage=config.LEVERAGE, margin_mode="isolated"),
            ["DOGE/USDT"],
        )
        self.assertFalse(status["ok"])
        self.assertEqual(status["margin_mode"]["reason"], "symbol_margin_mode_not_confirmed")

    def test_account_safety_reports_missing_hard_stop_for_open_position(self):
        status = account_safety.account_safety_status(
            FakeAccountExchange(
                dual_side=False,
                leverage=config.LEVERAGE,
                margin_mode=config.MARGIN_MODE,
                contracts=10,
                has_stop=False,
            ),
            ["DOGE/USDT"],
        )
        self.assertFalse(status["ok"])
        self.assertEqual(status["hard_stop"]["reason"], "open_position_without_hard_stop")

    def test_set_margin_mode_rejects_mismatched_confirmation(self):
        old_symbol = config.SYMBOL
        old_margin = config.MARGIN_MODE
        try:
            config.SYMBOL = "DOGE/USDT"
            config.MARGIN_MODE = "cross"
            exchange = FakeAccountExchange()
            exchange.set_margin_mode = lambda margin_mode, symbol, params=None: {"symbol": "DOGEUSDT", "marginMode": "isolated"}
            self.assertFalse(order_manager.set_margin_mode(exchange))
        finally:
            config.SYMBOL = old_symbol
            config.MARGIN_MODE = old_margin

    def test_set_leverage_rejects_mismatched_confirmation(self):
        old_leverage = config.LEVERAGE
        old_symbol = config.SYMBOL
        try:
            config.LEVERAGE = 10
            config.SYMBOL = "DOGE/USDT"
            exchange = FakeAccountExchange(dual_side=False, leverage=5)
            exchange.set_leverage = lambda leverage, symbol, params=None: {"symbol": "DOGEUSDT", "leverage": 5}
            self.assertFalse(order_manager.set_leverage(exchange))
        finally:
            config.LEVERAGE = old_leverage
            config.SYMBOL = old_symbol

    def test_ops_status_can_include_exchange_safety(self):
        original = ops_status._exchange_safety_status
        try:
            ops_status._exchange_safety_status = lambda: {"ok": True, "position_mode": {"mode": "one_way"}}
            status = ops_status.build_status(include_exchange=True)
            self.assertTrue(status["exchange_safety"]["ok"])
            self.assertEqual(status["exchange_safety"]["position_mode"]["mode"], "one_way")
            self.assertEqual(status["state_scope"], "paper")
            self.assertFalse(status["compare_live_state_positions"])
            self.assertIn("alerts", status)
            self.assertIn("alert_count", status)
        finally:
            ops_status._exchange_safety_status = original

    def test_alerts_skip_live_state_mismatch_for_paper_scope(self):
        rows = alerts.build_alerts({
            "run_tag": "unit",
            "heartbeat_status": "ok",
            "heartbeat_stale": False,
            "recent_errors": 0,
            "open_positions": 1,
            "live_state_positions": 0,
            "compare_live_state_positions": False,
            "testnet": True,
            "live_trading_approved": False,
        })
        self.assertNotIn("state_position_mismatch", {row["code"] for row in rows})

    def test_alerts_detect_live_state_mismatch_when_enabled(self):
        rows = alerts.build_alerts({
            "run_tag": "unit",
            "heartbeat_status": "ok",
            "heartbeat_stale": False,
            "recent_errors": 0,
            "open_positions": 1,
            "live_state_positions": 0,
            "compare_live_state_positions": True,
            "testnet": True,
            "live_trading_approved": False,
        })
        self.assertIn("state_position_mismatch", {row["code"] for row in rows})

    def test_alerts_detect_stale_heartbeat_and_errors(self):
        rows = alerts.build_alerts({
            "run_tag": "unit",
            "heartbeat_status": "ok",
            "heartbeat_stale": True,
            "heartbeat_age_minutes": 999,
            "recent_errors": 2,
            "open_positions": 0,
            "live_state_positions": 0,
            "testnet": True,
            "live_trading_approved": False,
        })
        codes = {row["code"] for row in rows}
        severities = {row["code"]: row["severity"] for row in rows}
        self.assertIn("heartbeat_stale", codes)
        self.assertIn("recent_runtime_errors", codes)
        self.assertEqual(severities["heartbeat_stale"], "critical")
        self.assertEqual(severities["recent_runtime_errors"], "warning")

    def test_alerts_write_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alerts.jsonl"
            count = alerts.write_alerts([
                {
                    "code": "unit_alert",
                    "severity": "warning",
                    "message": "Unit alert.",
                    "run_tag": "unit",
                    "details": {"value": 1},
                }
            ], str(path))
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(count, 1)
            self.assertEqual(rows[0]["code"], "unit_alert")
            self.assertEqual(rows[0]["details"]["value"], 1)

    def test_decision_snapshot_writes_trade_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trade_decisions.jsonl"
            bar = pd.Series(
                {
                    "open": 1.0,
                    "high": 1.2,
                    "low": 0.9,
                    "close": 1.1,
                    "volume": 1000.0,
                    "volume_ma": 900.0,
                    "atr": 0.05,
                    "rsi": 55.0,
                    "adx": 30.0,
                    "regime": "trend",
                    "daily_trend": 1,
                    "weekly_trend": 1,
                    "flow_fresh": True,
                },
                name=pd.Timestamp("2026-05-01 04:00:00"),
            )
            snapshot = decision_snapshots.build_entry_snapshot(
                symbol="DOGE/USDT",
                timeframe="4h",
                signal="long",
                bar=bar,
                equity=1000.0,
                free_balance=900.0,
                risk_base_balance=1000.0,
                global_open_count=0,
                max_open_positions=2,
                base_risk=0.04,
                effective_risk=0.03,
                risk_multiplier=0.75,
                risk_reasons=("weekly_open",),
                price=1.1,
                atr=0.05,
            )
            out = decision_snapshots.attach_order_result(snapshot, {
                "side": "long",
                "entry": 1.1,
                "size": 12,
                "sl": 1.0,
                "hard_sl": 0.95,
                "sl_order_id": "sl-1",
                "entry_client_order_id": "entry-cid",
                "sl_client_order_id": "sl-cid",
            })
            decision_snapshots.write_snapshot(out, str(path))
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["status"], "opened")
            self.assertEqual(rows[0]["symbol"], "DOGE/USDT")
            self.assertEqual(rows[0]["bar"]["rsi"], 55.0)
            self.assertEqual(rows[0]["risk_reasons"], ["weekly_open"])
            self.assertEqual(rows[0]["result"]["entry_client_order_id"], "entry-cid")

    def test_order_events_append_jsonl(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.jsonl"
                config.ORDER_EVENTS_JSONL = str(path)
                order_events.record("unit_test_event", nested={"value": 1})
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["event_type"], "unit_test_event")
                self.assertEqual(rows[0]["nested"]["value"], 1)
        finally:
            config.ORDER_EVENTS_JSONL = old_path

    def test_kill_switch_dry_run_only_plans_actions(self):
        exchange = KillSwitchExchange()
        report = emergency_kill_switch.run_kill_switch(exchange, ["DOGE/USDT"], execute=False)
        self.assertFalse(report["execute"])
        self.assertEqual(report["totals"]["open_orders"], 1)
        self.assertEqual(report["totals"]["positions"], 1)
        self.assertEqual(exchange.cancelled, [])
        self.assertEqual(exchange.created_orders, [])

    def test_kill_switch_execute_cancels_and_reduce_only_closes(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_flag = getattr(config, "TRADING_DISABLED_FLAG", "trading_disabled.flag")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.TRADING_DISABLED_FLAG = str(Path(tmp) / "trading_disabled.flag")
                exchange = KillSwitchExchange()
                report = emergency_kill_switch.run_kill_switch(exchange, ["DOGE/USDT"], execute=True)
                self.assertEqual(report["totals"]["cancelled"], 1)
                self.assertEqual(report["totals"]["closed"], 1)
                self.assertTrue(Path(report["trading_disabled_flag"]).exists())
                self.assertEqual(exchange.cancelled[0]["order_id"], "stop-1")
                self.assertEqual(exchange.created_orders[0]["side"], "sell")
                self.assertEqual(exchange.created_orders[0]["amount"], 12.0)
                self.assertTrue(exchange.created_orders[0]["params"]["reduceOnly"])
                self.assertIn("newClientOrderId", exchange.created_orders[0]["params"])
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.TRADING_DISABLED_FLAG = old_flag

    def test_close_position_records_order_events(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.jsonl"
                config.ORDER_EVENTS_JSONL = str(path)
                config.SYMBOL = "SOL/USDT"
                exchange = FakeExchange()
                ok = order_manager.close_position_market(exchange, "long", 1.25)
                self.assertTrue(ok)
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                event_types = [row["event_type"] for row in rows]
                self.assertIn("close_cancel_all_error", event_types)
                self.assertIn("close_order_submit", event_types)
                self.assertIn("close_order_ack", event_types)
                self.assertIn("close_fill_resolved", event_types)
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_close_position_partial_fill_retains_existing_protection(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "events.jsonl"
                config.ORDER_EVENTS_JSONL = str(path)
                config.SYMBOL = "DOGE/USDT"
                exchange = PartialCloseExchange()
                ok = order_manager.close_position_market(exchange, "long", 20.0)
                self.assertFalse(ok)
                self.assertEqual(exchange.cancel_all_calls, [])
                rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
                self.assertIn("close_not_fully_filled_protection_retained", {row["event_type"] for row in rows})
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_client_order_id_deterministic_on_retry(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                cid = order_manager.client_order_id(
                    "DOGE/USDT",
                    "entry",
                    epoch_ms=1770000000000,
                    nonce8="abc12345",
                )
                exchange = RetryCreateExchange()
                order, resolved_cid, duplicate = order_manager._create_order_idempotent(
                    exchange,
                    symbol="DOGE/USDT",
                    type="market",
                    side="buy",
                    amount=2.0,
                    intent="entry",
                    params={"reduceOnly": False},
                    client_order_id_value=cid,
                )
                self.assertFalse(duplicate)
                self.assertEqual(resolved_cid, cid)
                self.assertEqual(order["clientOrderId"], cid)
                self.assertEqual(len(exchange.created_params), 2)
                self.assertEqual(exchange.created_params[0]["newClientOrderId"], cid)
                self.assertEqual(exchange.created_params[1]["newClientOrderId"], cid)
                long_cid = order_manager.client_order_id(
                    "1000PEPE/USDT",
                    "trailing_sl",
                    epoch_ms=1770000000000,
                    nonce8="abc12345",
                )
                self.assertLessEqual(len(long_cid), 36)
        finally:
            config.ORDER_EVENTS_JSONL = old_path

    def test_duplicate_order_id_recognized_and_reconciled(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.SYMBOL = "DOGE/USDT"
                cid = order_manager.client_order_id("DOGE/USDT", "entry", epoch_ms=1770000000000, nonce8="dup12345")
                exchange = DuplicateCreateExchange()
                order, resolved_cid, duplicate = order_manager._create_order_idempotent(
                    exchange,
                    symbol="DOGE/USDT",
                    type="market",
                    side="buy",
                    amount=2.0,
                    intent="entry",
                    client_order_id_value=cid,
                )
                self.assertTrue(duplicate)
                self.assertEqual(resolved_cid, cid)
                self.assertEqual(order["id"], "existing-order")
                self.assertEqual(exchange.raw_params["origClientOrderId"], cid)
                self.assertIsNone(exchange.fetch_params)
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_fetch_order_by_client_id_uses_none_id_fallback(self):
        old_symbol = config.SYMBOL
        try:
            config.SYMBOL = "DOGE/USDT"
            exchange = FetchFallbackExchange()
            order = order_manager._fetch_order_by_client_id(exchange, "cid-123", "DOGE/USDT")
            self.assertEqual(order["id"], "fallback-existing-order")
            self.assertIsNone(exchange.fetch_order_id)
            self.assertEqual(exchange.fetch_symbol, "DOGE/USDT")
            self.assertEqual(exchange.fetch_params["origClientOrderId"], "cid-123")
        finally:
            config.SYMBOL = old_symbol

    def test_reject_error_codes_are_not_duplicate_recovery(self):
        messages = [
            "-2010 NEW_ORDER_REJECTED insufficient balance",
            "-2027 EXCEEDED_MAX_ALLOWABLE_POSITION",
            "-4015 CLIENT_ORDER_ID_INVALID",
        ]
        for message in messages:
            with self.subTest(message=message):
                exchange = RejectCodeExchange(message)
                with self.assertRaises(ccxt.ExchangeError):
                    order_manager._create_order_idempotent(
                        exchange,
                        symbol="DOGE/USDT",
                        type="market",
                        side="buy",
                        amount=2.0,
                        intent="entry",
                        client_order_id_value="cid-123",
                    )
                self.assertFalse(exchange.fetch_called)

    def test_partial_fill_abort_policy_closes_filled_only(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_policy = getattr(config, "PARTIAL_FILL_POLICY", "abort")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.PARTIAL_FILL_POLICY = "abort"
                config.SYMBOL = "DOGE/USDT"
                exchange = PartialFillExchange()
                order = {
                    "id": "partial-entry",
                    "clientOrderId": "entry-cid",
                    "amount": 20.0,
                    "filled": 12.0,
                    "remaining": 8.0,
                    "average": 0.50,
                }
                fill = order_manager._resolve_market_fill(
                    exchange,
                    order,
                    fallback_price=0.50,
                    fallback_size=20.0,
                    context="entry",
                    position_side="long",
                )
                self.assertTrue(fill.partial)
                self.assertTrue(fill.aborted)
                self.assertEqual(fill.filled_size, 12.0)
                self.assertEqual(exchange.cancelled[0]["order_id"], "partial-entry")
                self.assertEqual(exchange.created_orders[0]["side"], "sell")
                self.assertEqual(exchange.created_orders[0]["amount"], 12.0)
                self.assertTrue(exchange.created_orders[0]["params"]["reduceOnly"])
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.PARTIAL_FILL_POLICY = old_policy
            config.SYMBOL = old_symbol

    def test_zero_fill_does_not_fallback_to_full_size(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.SYMBOL = "DOGE/USDT"
                exchange = PartialFillExchange()
                order = {
                    "id": "zero-fill-entry",
                    "clientOrderId": "entry-cid",
                    "amount": 20.0,
                    "filled": 0.0,
                    "remaining": 20.0,
                    "average": 0.0,
                }
                fill = order_manager._resolve_market_fill(
                    exchange,
                    order,
                    fallback_price=0.50,
                    fallback_size=20.0,
                    context="entry",
                    position_side="long",
                )
                self.assertEqual(fill.filled_size, 0.0)
                self.assertEqual(fill.remaining_size, 20.0)
                self.assertTrue(fill.partial)
                self.assertTrue(fill.aborted)
                self.assertEqual(exchange.cancelled[0]["order_id"], "zero-fill-entry")
                self.assertEqual(exchange.created_orders, [])
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_partial_fill_accept_policy_sizes_sl_to_filled(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_policy = getattr(config, "PARTIAL_FILL_POLICY", "abort")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.PARTIAL_FILL_POLICY = "accept"
                config.SYMBOL = "DOGE/USDT"
                partial_exchange = PartialFillExchange()
                order = {
                    "id": "partial-entry",
                    "clientOrderId": "entry-cid",
                    "amount": 20.0,
                    "filled": 12.0,
                    "remaining": 8.0,
                    "average": 0.50,
                }
                fill = order_manager._resolve_market_fill(
                    partial_exchange,
                    order,
                    fallback_price=0.50,
                    fallback_size=20.0,
                    context="entry",
                    position_side="long",
                )
                self.assertTrue(fill.partial)
                self.assertFalse(fill.aborted)
                stop_exchange = StopOrderExchange()
                sl_order = order_manager._create_sl_order(
                    stop_exchange,
                    "sell",
                    fill.filled_size,
                    0.4999,
                    ref_price=0.50,
                    intent="hard_sl",
                )
                self.assertIsNotNone(sl_order)
                self.assertEqual(stop_exchange.created_orders[0]["amount"], 12.0)
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.PARTIAL_FILL_POLICY = old_policy
            config.SYMBOL = old_symbol

    def test_trailing_sl_cleanup_cancels_orphan_reduce_only_stops(self):
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_symbol = config.SYMBOL
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.SYMBOL = "DOGE/USDT"
                exchange = TrailingCleanupExchange()
                position = {
                    "side": "long",
                    "entry": 0.50,
                    "size": 12.0,
                    "sl": 0.45,
                    "hard_sl": 0.44,
                    "sl_order_id": "old-stop",
                    "atr": 0.01,
                }
                order_manager.update_trailing_sl(exchange, position, current_price=0.60, extreme=0.60)
                self.assertEqual(position["sl_order_id"], "new-stop")
                self.assertIn("old-stop", exchange.cancelled)
                self.assertIn("stale-stop", exchange.cancelled)
                self.assertNotIn("buy-stop", exchange.cancelled)
                remaining_ids = {o["id"] for o in exchange.open_orders}
                self.assertIn("new-stop", remaining_ids)
                self.assertIn("buy-stop", remaining_ids)
                self.assertNotIn("old-stop", remaining_ids)
                self.assertNotIn("stale-stop", remaining_ids)
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_exchange_filters_floor_market_amount_and_notional(self):
        exchange_filters.clear_cache()
        result = exchange_filters.validate_entry_order(
            FakeExchangeInfo(),
            "DOGE/USDT",
            "buy",
            amount=12.9,
            ref_price=0.50,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.amount, 12.0)
        self.assertEqual(result.notional, 6.0)

    def test_exchange_filters_block_min_notional(self):
        exchange_filters.clear_cache()
        result = exchange_filters.validate_entry_order(
            FakeExchangeInfo(),
            "DOGE/USDT",
            "buy",
            amount=9,
            ref_price=0.50,
        )
        self.assertFalse(result.ok)
        self.assertIn("min_notional", result.reason)

    def test_exchange_filters_adjust_stop_price_to_tick(self):
        exchange_filters.clear_cache()
        sell_result = exchange_filters.validate_stop_order(
            FakeExchangeInfo(),
            "DOGE/USDT",
            "sell",
            amount=12,
            stop_price=0.49996,
            ref_price=0.50,
        )
        buy_result = exchange_filters.validate_stop_order(
            FakeExchangeInfo(),
            "DOGE/USDT",
            "buy",
            amount=12,
            stop_price=0.50004,
            ref_price=0.50,
        )
        self.assertTrue(sell_result.ok)
        self.assertEqual(sell_result.price, 0.4999)
        self.assertTrue(buy_result.ok)
        self.assertEqual(buy_result.price, 0.5001)

    def test_exchange_filters_normalize_market_amount_to_step(self):
        exchange_filters.clear_cache()
        result = exchange_filters.normalize_market_amount(
            FakeExchangeInfo(),
            "DOGE/USDT",
            12.9,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.amount, 12.0)

    def test_exchange_filters_cache_ttl_and_refresh(self):
        old_ttl = config.EXCHANGE_FILTER_CACHE_TTL_SECONDS
        try:
            exchange_filters.clear_cache()
            exchange = CountingExchangeInfo()
            config.EXCHANGE_FILTER_CACHE_TTL_SECONDS = 3600
            first = exchange_filters.get_symbol_filters(exchange, "DOGE/USDT")
            second = exchange_filters.get_symbol_filters(exchange, "DOGE/USDT")
            self.assertEqual(first, second)
            self.assertEqual(exchange.calls, 1)

            exchange_filters.refresh_symbol_filters(exchange, "DOGE/USDT")
            self.assertEqual(exchange.calls, 2)

            config.EXCHANGE_FILTER_CACHE_TTL_SECONDS = 0
            exchange_filters.get_symbol_filters(exchange, "DOGE/USDT")
            self.assertEqual(exchange.calls, 3)
        finally:
            config.EXCHANGE_FILTER_CACHE_TTL_SECONDS = old_ttl
            exchange_filters.clear_cache()

    def test_hard_stop_from_soft_preserves_small_price_precision(self):
        self.assertAlmostEqual(
            execution_guard.hard_stop_from_soft(0.123456, 0.000321, "long"),
            0.123135,
            places=9,
        )
        self.assertAlmostEqual(
            execution_guard.hard_stop_from_soft(0.123456, 0.000321, "short"),
            0.123777,
            places=9,
        )

    def test_timeframe_to_timedelta(self):
        self.assertEqual(execution_guard.timeframe_to_timedelta("15m").total_seconds(), 900)
        self.assertEqual(execution_guard.timeframe_to_timedelta("2h").total_seconds(), 7200)
        self.assertEqual(execution_guard.timeframe_to_timedelta("1d").total_seconds(), 86400)

    def test_closed_bar_age_guard_accepts_recent_closed_bar(self):
        idx = pd.to_datetime([
            "2026-05-01 00:00:00",
            "2026-05-01 04:00:00",
            "2026-05-01 08:00:00",
        ])
        df = pd.DataFrame({"close": [1, 2, 3]}, index=idx)
        decision = execution_guard.closed_bar_age_decision(
            df,
            "4h",
            now=pd.Timestamp("2026-05-01 08:30:00", tz="UTC"),
        )
        self.assertTrue(decision.ok)
        self.assertEqual(decision.age_minutes, 30.0)

    def test_closed_bar_age_guard_blocks_stale_closed_bar(self):
        idx = pd.to_datetime([
            "2026-05-01 00:00:00",
            "2026-05-01 04:00:00",
            "2026-05-01 08:00:00",
        ])
        df = pd.DataFrame({"close": [1, 2, 3]}, index=idx)
        decision = execution_guard.closed_bar_age_decision(
            df,
            "4h",
            now=pd.Timestamp("2026-05-01 14:30:00", tz="UTC"),
        )
        self.assertFalse(decision.ok)
        self.assertEqual(decision.reason, "closed_bar_stale")
        self.assertEqual(decision.max_age_minutes, 300.0)

    def test_reduce_only_close_amount_uses_market_lot_step(self):
        old_symbol = config.SYMBOL
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.SYMBOL = "DOGE/USDT"
                exchange = FakeExchange()
                ok = order_manager.close_position_market(exchange, "long", 12.9)
                self.assertTrue(ok)
                self.assertEqual(exchange.created_orders[0]["amount"], 12.0)
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_emergency_close_amount_uses_market_lot_step(self):
        old_symbol = config.SYMBOL
        old_path = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.SYMBOL = "DOGE/USDT"
                exchange = PartialFillExchange()
                order_manager._safe_close_market(exchange, "long", 12.9)
                self.assertEqual(exchange.created_orders[0]["amount"], 12.0)
        finally:
            config.ORDER_EVENTS_JSONL = old_path
            config.SYMBOL = old_symbol

    def test_exchange_filters_block_percent_price_outlier(self):
        exchange_filters.clear_cache()
        result = exchange_filters.validate_stop_order(
            FakeExchangeInfo(),
            "DOGE/USDT",
            "sell",
            amount=12,
            stop_price=0.40,
            ref_price=0.50,
        )
        self.assertFalse(result.ok)
        self.assertIn("percent_price_low", result.reason)

    def test_market_close_still_runs_when_cancel_fails(self):
        old_symbol = config.SYMBOL
        old_events = getattr(config, "ORDER_EVENTS_JSONL", "order_events.jsonl")
        old_recv = getattr(config, "RECV_WINDOW_MS", 5000)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config.RECV_WINDOW_MS = 7000
                config.ORDER_EVENTS_JSONL = str(Path(tmp) / "events.jsonl")
                config.SYMBOL = "SOL/USDT"
                exchange = FakeExchange()
                ok = order_manager.close_position_market(exchange, "long", 1.25)
                self.assertTrue(ok)
                self.assertEqual(len(exchange.created_orders), 1)
                self.assertEqual(exchange.created_orders[0]["side"], "sell")
                self.assertTrue(exchange.created_orders[0]["params"]["reduceOnly"])
                self.assertEqual(exchange.created_orders[0]["params"]["recvWindow"], 7000)
                self.assertEqual(exchange.cancel_all_params[0]["recvWindow"], 7000)
        finally:
            config.SYMBOL = old_symbol
            config.ORDER_EVENTS_JSONL = old_events
            config.RECV_WINDOW_MS = old_recv

    def test_flow_ttl_marks_old_bucket_stale(self):
        old_max_age = getattr(config, "FLOW_MAX_AGE_MINUTES", 300)
        try:
            config.FLOW_MAX_AGE_MINUTES = 60
            df = pd.DataFrame(
                {"close": [10.0, 10.5]},
                index=pd.to_datetime(["2026-01-01 04:00:00", "2026-01-01 08:00:00"]),
            )
            flow = pd.DataFrame(
                {"flow_taker_buy_ratio": [0.9]},
                index=pd.to_datetime(["2026-01-01 00:00:00"]),
            )
            out = flow_data.add_flow_indicators(df, flow, period="4h")
            self.assertTrue(bool(out.loc[pd.Timestamp("2026-01-01 04:00:00"), "flow_fresh"]))
            self.assertFalse(bool(out.loc[pd.Timestamp("2026-01-01 08:00:00"), "flow_fresh"]))
            self.assertTrue(pd.isna(out.loc[pd.Timestamp("2026-01-01 08:00:00"), "flow_taker_buy_ratio"]))
        finally:
            config.FLOW_MAX_AGE_MINUTES = old_max_age

    def test_stale_flow_does_not_change_risk(self):
        decision = risk._flow_risk_decision(
            {"flow_fresh": False, "flow_taker_buy_ratio": 0.99},
            "long",
            close=101.0,
            open_=100.0,
        )
        self.assertEqual(decision.multiplier, 1.0)
        self.assertIn("flow:stale", decision.reasons)

    def test_legacy_risk_management_is_quarantined(self):
        with self.assertRaisesRegex(RuntimeError, "deprecated"):
            risk_management.calculate_position_size(1000, 0.1, 5, 50000)

    def test_paper_runner_lock_blocks_second_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "paper.lock"
            with paper_runner.PaperRunnerLock(lock_path):
                with self.assertRaises(RuntimeError):
                    with paper_runner.PaperRunnerLock(lock_path):
                        pass
            self.assertFalse(lock_path.exists())

    def test_paper_runner_lock_refresh_updates_heartbeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "paper.lock"
            with paper_runner.PaperRunnerLock(lock_path) as lock:
                first = json.loads(lock_path.read_text(encoding="utf-8"))
                first_mtime = lock_path.stat().st_mtime_ns
                time.sleep(0.01)
                lock.refresh()
                second = json.loads(lock_path.read_text(encoding="utf-8"))
                second_mtime = lock_path.stat().st_mtime_ns
                self.assertEqual(second["created_at"], first["created_at"])
                self.assertNotEqual(second["updated_at"], first["updated_at"])
                self.assertGreater(second_mtime, first_mtime)
            self.assertFalse(lock_path.exists())

    def test_paper_csv_append_expands_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "paper.csv"
            paper_runner._append_csv(str(csv_path), [{"symbol": "SOL/USDT", "action": "no_signal"}])
            paper_runner._append_csv(str(csv_path), [{"symbol": "ETH/USDT", "action": "no_signal", "flow_fresh": True}])
            rows = list(pd.read_csv(csv_path).to_dict("records"))
            self.assertIn("flow_fresh", pd.read_csv(csv_path).columns)
            self.assertEqual(rows[-1]["flow_fresh"], True)

    def test_paper_csv_append_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "nested" / "paper.csv"
            paper_runner._append_csv(str(csv_path), [{"symbol": "SOL/USDT", "action": "no_signal"}])
            self.assertTrue(csv_path.exists())
            self.assertEqual(pd.read_csv(csv_path).iloc[0]["symbol"], "SOL/USDT")

    def test_paper_runner_updates_position_excursions(self):
        pos = {
            "symbol": "DOGE/USDT",
            "side": "long",
            "entry": 1.0,
            "size": 10.0,
            "entry_equity": 100.0,
        }
        bar = pd.Series({"high": 1.3, "low": 0.9})
        paper_runner._update_position_excursions(pos, bar)
        self.assertAlmostEqual(pos["max_favorable"], 3.0)
        self.assertAlmostEqual(pos["max_adverse"], 1.0)
        self.assertAlmostEqual(pos["max_favorable_pct"], 3.0)
        self.assertAlmostEqual(pos["max_adverse_pct"], 1.0)

    def test_same_closed_bar_as_entry_guard(self):
        bar = pd.Series({"close": 1.0}, name=pd.Timestamp("2026-05-04 00:00:00"))
        pos = {"entry_time": "2026-05-04T00:00:00"}
        self.assertTrue(execution_guard.same_closed_bar_as_entry(pos, bar))
        other = pd.Series({"close": 1.0}, name=pd.Timestamp("2026-05-04 04:00:00"))
        self.assertFalse(execution_guard.same_closed_bar_as_entry(pos, other))

    def test_paper_runner_skips_same_bar_position_management(self):
        bar_time = pd.Timestamp("2026-05-04 00:00:00")
        frame = pd.DataFrame(
            [
                {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "atr": 0.1},
                {"open": 1.0, "high": 1.1, "low": 0.5, "close": 0.9, "atr": 0.1},
                {"open": 0.9, "high": 1.0, "low": 0.8, "close": 0.95, "atr": 0.1},
            ],
            index=[
                pd.Timestamp("2026-05-03 20:00:00"),
                bar_time,
                pd.Timestamp("2026-05-04 04:00:00"),
            ],
        )
        state = {
            "wallet": 1000.0,
            "positions": {
                "DOGE/USDT": {
                    "symbol": "DOGE/USDT",
                    "side": "long",
                    "entry": 1.0,
                    "size": 100.0,
                    "sl": 0.8,
                    "hard_sl": 0.7,
                    "atr": 0.1,
                    "extreme": 1.0,
                    "entry_time": bar_time.isoformat(),
                    "entry_equity": 1000.0,
                }
            },
        }
        trades, closed_bars = paper_runner._manage_positions(state, {"DOGE/USDT": frame})
        self.assertEqual(trades, [])
        self.assertEqual(closed_bars, {})
        self.assertIn("DOGE/USDT", state["positions"])
        self.assertEqual(state["wallet"], 1000.0)

    def test_paper_runner_same_bar_reentry_helper(self):
        bar = pd.Series({"close": 1.0}, name=pd.Timestamp("2026-05-04 00:00:00"))
        closed_bars = {"DOGE/USDT": "2026-05-04T00:00:00"}
        self.assertTrue(paper_runner._closed_on_current_bar(closed_bars, "DOGE/USDT", bar))
        self.assertFalse(paper_runner._closed_on_current_bar(closed_bars, "LINK/USDT", bar))

    def test_paper_report_latest_decision_by_symbol(self):
        rows = [
            {"symbol": "DOGE/USDT", "action": "no_signal", "bar_time": "old", "close": "1.0"},
            {"symbol": "LINK/USDT", "action": "skip", "bar_time": "latest", "close": "2.0"},
            {"symbol": "DOGE/USDT", "action": "paper_open", "bar_time": "latest", "close": "1.5"},
        ]
        latest = paper_report.latest_decisions_by_symbol(rows, ["DOGE/USDT", "LINK/USDT"])
        self.assertEqual([row["symbol"] for row in latest], ["DOGE/USDT", "LINK/USDT"])
        self.assertEqual(latest[0]["action"], "paper_open")
        self.assertEqual(latest[0]["close"], 1.5)

    def test_paper_report_builds_from_runtime_files(self):
        old_symbols = config.SYMBOLS
        old_heartbeat = getattr(config, "PAPER_HEARTBEAT_FILE", "paper_heartbeat.json")
        old_decisions = getattr(config, "PAPER_DECISIONS_CSV", "paper_decisions.csv")
        old_equity = getattr(config, "PAPER_EQUITY_CSV", "paper_equity.csv")
        old_trades = getattr(config, "PAPER_TRADES_CSV", "paper_trades.csv")
        old_errors = getattr(config, "PAPER_ERRORS_CSV", "paper_errors.csv")
        old_state = getattr(config, "PAPER_STATE_FILE", "paper_state.json")
        old_testnet = config.TESTNET
        old_live = config.LIVE_TRADING_APPROVED
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config.SYMBOLS = ["DOGE/USDT", "LINK/USDT"]
                config.TESTNET = True
                config.LIVE_TRADING_APPROVED = False
                config.PAPER_HEARTBEAT_FILE = str(root / "heartbeat.json")
                config.PAPER_DECISIONS_CSV = str(root / "decisions.csv")
                config.PAPER_EQUITY_CSV = str(root / "equity.csv")
                config.PAPER_TRADES_CSV = str(root / "trades.csv")
                config.PAPER_ERRORS_CSV = str(root / "errors.csv")
                config.PAPER_STATE_FILE = str(root / "state.json")

                heartbeat = {
                    "status": "ok",
                    "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                    "pid": 123,
                    "wallet": 1000.0,
                    "equity": 1001.0,
                    "open_positions": 0,
                }
                (root / "heartbeat.json").write_text(json.dumps(heartbeat), encoding="utf-8")
                paper_runner._append_csv(config.PAPER_DECISIONS_CSV, [
                    {"symbol": "DOGE/USDT", "action": "no_signal", "bar_time": "2026-01-01", "risk_mult": "1.0"},
                    {
                        "symbol": "LINK/USDT",
                        "action": "skip",
                        "bar_time": "2026-01-01",
                        "skipped_reason": "risk_block",
                    },
                ])
                paper_runner._append_csv(config.PAPER_EQUITY_CSV, [
                    {"wallet": 1000.0, "equity": 1001.0, "open_positions": 0}
                ])
                paper_runner._append_csv(config.PAPER_TRADES_CSV, [
                    {
                        "symbol": "DOGE/USDT",
                        "side": "long",
                        "exit_time": "2026-01-01",
                        "pnl": "5.5",
                        "pnl_return_pct": "0.55",
                        "exit_reason": "trend_exit",
                        "max_favorable_pct": "1.2",
                        "max_adverse_pct": "0.4",
                    }
                ])
                Path(config.PAPER_STATE_FILE).write_text(json.dumps({
                    "positions": {
                        "LINK/USDT": {
                            "side": "short",
                            "entry": 10.0,
                            "size": 2.0,
                            "sl": 11.0,
                            "risk_pct": 0.02,
                        }
                    }
                }), encoding="utf-8")

                report = paper_report.build_report(decision_limit=10)
                self.assertEqual(report["heartbeat"]["status"], "ok")
                self.assertEqual(report["recent"]["actions"]["no_signal"], 1)
                self.assertEqual(report["recent"]["actions"]["skip"], 1)
                self.assertEqual(report["recent"]["skips"]["risk_block"], 1)
                self.assertEqual(report["recent"]["trade_summary"]["total_pnl"], 5.5)
                self.assertEqual(report["recent"]["latest_trades"][0]["exit_reason"], "trend_exit")
                self.assertEqual(report["open_positions"][0]["symbol"], "LINK/USDT")
                self.assertEqual(report["warnings"], [])
        finally:
            config.SYMBOLS = old_symbols
            config.PAPER_HEARTBEAT_FILE = old_heartbeat
            config.PAPER_DECISIONS_CSV = old_decisions
            config.PAPER_EQUITY_CSV = old_equity
            config.PAPER_TRADES_CSV = old_trades
            config.PAPER_ERRORS_CSV = old_errors
            config.PAPER_STATE_FILE = old_state
            config.TESTNET = old_testnet
            config.LIVE_TRADING_APPROVED = old_live

    def test_paper_runtime_tagged_files_and_scaling_restore(self):
        old_files = {attr: getattr(config, attr) for attr in paper_runtime.PAPER_FILE_ATTRS}
        old_timeframe = config.TIMEFRAME
        old_flow_period = getattr(config, "FLOW_PERIOD", old_timeframe)
        old_donchian = config.DONCHIAN_PERIOD
        old_warmup = config.WARMUP_BARS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for attr, value in old_files.items():
                    setattr(config, attr, str(root / Path(value).name))

                with paper_runtime.temporary_paper_runtime(
                    tag="shadow 2h",
                    timeframe="2h",
                    scale_lookbacks=True,
                ):
                    self.assertEqual(config.PAPER_RUN_TAG, "shadow_2h")
                    self.assertEqual(config.TIMEFRAME, "2h")
                    self.assertEqual(config.FLOW_PERIOD, "2h")
                    self.assertEqual(config.DONCHIAN_PERIOD, old_donchian * 2)
                    self.assertEqual(config.WARMUP_BARS, old_warmup * 2)
                    self.assertEqual(
                        Path(config.PAPER_STATE_FILE).name,
                        "paper_shadow_2h_state.json",
                    )
                    self.assertEqual(
                        Path(config.PAPER_HEARTBEAT_FILE).name,
                        "paper_shadow_2h_heartbeat.json",
                    )

                self.assertEqual(config.TIMEFRAME, old_timeframe)
                self.assertEqual(config.FLOW_PERIOD, old_flow_period)
                self.assertEqual(config.DONCHIAN_PERIOD, old_donchian)
                self.assertEqual(config.WARMUP_BARS, old_warmup)
        finally:
            for attr, value in old_files.items():
                setattr(config, attr, value)

    def test_paper_report_reads_tagged_runtime_files(self):
        old_files = {attr: getattr(config, attr) for attr in paper_runtime.PAPER_FILE_ATTRS}
        old_symbols = config.SYMBOLS
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for attr, value in old_files.items():
                    setattr(config, attr, str(root / Path(value).name))
                config.SYMBOLS = ["DOGE/USDT"]

                with paper_runtime.temporary_paper_runtime(tag="shadow_2h", timeframe="2h"):
                    Path(config.PAPER_HEARTBEAT_FILE).write_text(json.dumps({
                        "status": "ok",
                        "updated_at": pd.Timestamp.now(tz="UTC").isoformat(),
                        "pid": 456,
                        "run_tag": "shadow_2h",
                        "timeframe": "2h",
                        "flow_period": "2h",
                        "scaled_lookbacks": True,
                        "wallet": 1000.0,
                        "equity": 1002.0,
                        "open_positions": 0,
                    }), encoding="utf-8")
                    paper_runner._append_csv(config.PAPER_DECISIONS_CSV, [{
                        "symbol": "DOGE/USDT",
                        "action": "no_signal",
                        "bar_time": "2026-01-01",
                        "close": "0.1",
                    }])

                with paper_runtime.temporary_paper_runtime(tag="shadow_2h"):
                    report = paper_report.build_report(decision_limit=10)

                self.assertEqual(report["runtime"]["run_tag"], "shadow_2h")
                self.assertEqual(report["runtime"]["timeframe"], "2h")
                self.assertEqual(report["heartbeat"]["equity"], 1002.0)
                self.assertEqual(report["recent"]["actions"]["no_signal"], 1)
        finally:
            config.SYMBOLS = old_symbols
            for attr, value in old_files.items():
                setattr(config, attr, value)

    def test_paper_decision_report_summarizes_daily_window(self):
        now = pd.Timestamp("2026-05-04T12:00:00Z")
        decisions = pd.DataFrame({
            "run_at_utc": [
                "2026-05-04T11:00:00Z",
                "2026-05-04T10:00:00Z",
                "2026-05-02T10:00:00Z",
            ],
            "action": ["paper_open", "skip", "no_signal"],
            "skipped_reason": ["", "orderbook_guard", ""],
        })
        trades = pd.DataFrame({
            "closed_at_utc": ["2026-05-04T11:30:00Z", "2026-05-02T10:00:00Z"],
            "pnl": ["5.0", "-2.0"],
        })
        errors = pd.DataFrame({"run_at_utc": ["2026-05-04T11:45:00Z"]})
        summary = paper_decision_report.summarize_window(
            decisions,
            trades,
            errors,
            pd.Timedelta(days=1),
            now=now,
        )
        self.assertEqual(summary["decision_rows"], 2)
        self.assertEqual(summary["actions"]["paper_open"], 1)
        self.assertEqual(summary["skips"]["orderbook_guard"], 1)
        self.assertEqual(summary["trades"], 1)
        self.assertEqual(summary["total_pnl"], 5.0)
        self.assertEqual(summary["errors"], 1)

    def test_carry_research_summarizes_positive_funding_edge(self):
        idx = pd.date_range("2026-01-01", periods=90, freq="8h", tz="UTC")
        rates = pd.DataFrame({"funding_rate": [0.0002] * len(idx)}, index=idx)
        summary = carry_research.summarize_funding_rates(
            rates,
            symbol="DOGE/USDT",
            earn_apr_benchmark_pct=6.0,
        )
        self.assertEqual(summary["samples"], 90)
        self.assertGreater(summary["gross_funding_apr_pct"], 20.0)
        self.assertTrue(summary["ok"])

    def test_carry_research_rejects_no_data(self):
        summary = carry_research.summarize_funding_rates(
            pd.DataFrame(columns=["funding_rate"]),
            symbol="DOGE/USDT",
        )
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["reason"], "no_funding_data")

    def test_legacy_walk_forward_accepts_weekly_data_argument(self):
        idx = pd.date_range("2026-01-01", periods=10, freq="4h")
        df_4h = pd.DataFrame(
            {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
            index=idx,
        )
        df_1d = pd.DataFrame(
            {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
            index=pd.date_range("2026-01-01", periods=2, freq="1D"),
        )
        df_1w = pd.DataFrame(
            {"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0},
            index=pd.date_range("2025-12-29", periods=1, freq="7D"),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            result = walk_forward.walk_forward(
                df_4h,
                df_1d,
                df_1w,
                train_bars=5,
                test_bars=3,
                roll_bars=3,
                warmup_bars=1,
            )
        self.assertTrue(result.empty)

    def test_protections_disabled_are_neutral(self):
        old_enabled = getattr(config, "PROTECTIONS_ENABLED", False)
        try:
            config.PROTECTIONS_ENABLED = False
            decision = protections.protection_decision(
                "SOL/USDT",
                pd.Timestamp("2026-01-02 00:00:00"),
                [{"symbol": "SOL/USDT", "exit_time": "2026-01-01 23:00:00", "result": "soft_sl", "pnl": -10}],
                equity=800,
                peak_equity=1000,
            )
            self.assertFalse(decision.block_new_entries)
            self.assertEqual(decision.multiplier, 1.0)
            self.assertEqual(decision.reasons, ())
        finally:
            config.PROTECTIONS_ENABLED = old_enabled

    def test_protections_stoploss_guard_blocks_when_enabled(self):
        old_enabled = getattr(config, "PROTECTIONS_ENABLED", False)
        old_limit = getattr(config, "PROTECTION_STOPLOSS_TRADE_LIMIT", 3)
        try:
            config.PROTECTIONS_ENABLED = True
            config.PROTECTION_STOPLOSS_TRADE_LIMIT = 2
            trades = [
                {"symbol": "SOL/USDT", "exit_time": "2026-01-01 04:00:00", "result": "soft_sl", "pnl": -5},
                {"symbol": "ETH/USDT", "exit_time": "2026-01-01 08:00:00", "result": "hard_sl", "pnl": -7},
            ]
            decision = protections.protection_decision("BNB/USDT", pd.Timestamp("2026-01-01 09:00:00"), trades)
            self.assertTrue(decision.block_new_entries)
            self.assertIn("protection:stoploss_guard", decision.reasons)
        finally:
            config.PROTECTIONS_ENABLED = old_enabled
            config.PROTECTION_STOPLOSS_TRADE_LIMIT = old_limit

    def test_exit_ladder_disabled_does_not_create_plan(self):
        old_enabled = getattr(config, "EXIT_LADDER_ENABLED", False)
        try:
            config.EXIT_LADDER_ENABLED = False
            self.assertEqual(exit_ladder.build_exit_plan(100.0, 5.0, "long"), [])
        finally:
            config.EXIT_LADDER_ENABLED = old_enabled

    def test_exit_ladder_breakeven_after_tp1(self):
        plan = exit_ladder.build_exit_plan(100.0, 5.0, "long", enabled=True)
        self.assertEqual(len(plan), 2)
        self.assertGreater(plan[0].target, 100.0)
        self.assertLessEqual(sum(step.close_fraction for step in plan), 1.0)
        self.assertEqual(exit_ladder.stop_after_filled_steps(100.0, "long", plan, 1), 100.0)

    def test_bias_audit_detects_future_dependent_feature(self):
        idx = pd.date_range("2026-01-01", periods=12, freq="4h")
        raw = pd.DataFrame(
            {"open": range(12), "high": range(1, 13), "low": range(12), "close": range(12), "volume": 1.0},
            index=idx,
        )

        def add_future(df):
            df = df.copy()
            df["future_close"] = df["close"].shift(-1)
            return df

        issues = bias_audit.audit_indicator_stability(
            raw,
            add_features=add_future,
            columns=("future_close",),
            min_prefix=5,
            sample_step=1,
        )
        self.assertTrue(issues)

    def test_bias_audit_accepts_past_only_feature(self):
        idx = pd.date_range("2026-01-01", periods=12, freq="4h")
        raw = pd.DataFrame(
            {"open": range(12), "high": range(1, 13), "low": range(12), "close": range(12), "volume": 1.0},
            index=idx,
        )

        def add_past(df):
            df = df.copy()
            df["past_mean"] = df["close"].rolling(3).mean()
            return df

        issues = bias_audit.audit_indicator_stability(
            raw,
            add_features=add_past,
            columns=("past_mean",),
            min_prefix=5,
            sample_step=1,
        )
        self.assertEqual(issues, [])

    def test_bias_audit_report_serializes_issue(self):
        issue = bias_audit.AuditIssue(
            timestamp=pd.Timestamp("2026-01-01", tz="UTC"),
            column="atr",
            full_value=1.0,
            prefix_value=2.0,
            diff=1.0,
        )
        row = bias_audit_report.issue_to_dict(issue)
        self.assertEqual(row["column"], "atr")
        self.assertEqual(row["diff"], 1.0)
        self.assertIn("2026-01-01", row["timestamp"])

    def test_pair_universe_disabled_keeps_symbols(self):
        old_enabled = getattr(config, "PAIR_UNIVERSE_ENABLED", False)
        try:
            config.PAIR_UNIVERSE_ENABLED = False
            self.assertEqual(pair_universe.select_symbols(["SOL/USDT"], {}), ["SOL/USDT"])
        finally:
            config.PAIR_UNIVERSE_ENABLED = old_enabled

    def test_pair_universe_rejects_too_few_bars(self):
        df = pd.DataFrame(
            {"close": [100.0, 101.0], "volume": [1.0, 1.0], "atr": [2.0, 2.0]},
            index=pd.date_range("2026-01-01", periods=2, freq="4h"),
        )
        score = pair_universe.score_pair("TEST/USDT", {"df": df})
        self.assertFalse(score.tradable)
        self.assertIn("pair:too_few_bars", score.reasons)

    def test_twap_plan_splits_large_notional_when_enabled(self):
        plan = twap_execution.build_twap_plan(
            notional=5_000.0,
            price=100.0,
            enabled=True,
            slice_notional=1_000.0,
            max_slices=10,
            interval_seconds=30,
        )
        self.assertEqual(len(plan), 5)
        self.assertEqual(plan[-1].delay_seconds, 120)
        self.assertAlmostEqual(sum(item.notional for item in plan), 5_000.0)

    def test_twap_planner_is_marked_passive_only(self):
        self.assertTrue(twap_execution.PASSIVE_ONLY)
        self.assertFalse(twap_execution.LIVE_ORDER_FLOW_WIRED)
        with self.assertRaisesRegex(NotImplementedError, "passive slice planner"):
            twap_execution.raise_if_live_execution_requested()

    def test_trade_executor_partial_step_is_passive_contract(self):
        old_enabled = getattr(config, "EXIT_LADDER_ENABLED", False)
        try:
            config.EXIT_LADDER_ENABLED = True
            trade = trade_executor.ManagedTrade(
                symbol="SOL/USDT",
                side="long",
                entry=100.0,
                size=1.0,
                atr=5.0,
                entry_time=pd.Timestamp("2026-01-01"),
                sl=90.0,
                hard_sl=85.0,
            )
            trade.activate()
            bar = pd.Series(
                {"open": 100.0, "high": 111.0, "low": 100.0, "close": 110.0, "atr": 5.0, "volume": 1.0},
                name=pd.Timestamp("2026-01-01 04:00:00"),
            )
            events = trade.update_from_bar(bar)
            self.assertTrue(any(event["event"] == "partial_close" for event in events))
            self.assertEqual(trade.filled_exit_steps, 1)
            self.assertGreaterEqual(trade.sl, 100.0)
            self.assertEqual(trade.status, trade_executor.ExecutorStatus.ACTIVE)
        finally:
            config.EXIT_LADDER_ENABLED = old_enabled

    def test_trade_executor_is_marked_passive_only(self):
        self.assertTrue(trade_executor.PASSIVE_ONLY)
        self.assertFalse(trade_executor.LIVE_ORDER_FLOW_WIRED)
        with self.assertRaisesRegex(NotImplementedError, "passive lifecycle model"):
            trade_executor.raise_if_live_execution_requested()

    def test_passive_execution_helpers_are_not_wired_into_order_flow(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("bot.py", "order_manager.py", "paper_runner.py"):
            text = (root / filename).read_text(encoding="utf-8")
            self.assertNotIn("import twap_execution", text, filename)
            self.assertNotIn("from twap_execution", text, filename)
            self.assertNotIn("import trade_executor", text, filename)
            self.assertNotIn("from trade_executor", text, filename)

    def test_requirements_are_exactly_pinned(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("requirements.txt", "requirements-dev.txt"):
            for line in (root / filename).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-r "):
                    continue
                self.assertIn("==", line, f"{filename}: {line}")
                self.assertNotIn(">=", line, f"{filename}: {line}")

    def test_candidate_sweep_generates_current_combo_once(self):
        combos = portfolio_candidate_sweep.generate_combos(
            ["SOL/USDT", "ETH/USDT", "BNB/USDT"],
            min_size=2,
            max_size=3,
            include_current=True,
        )
        self.assertEqual(combos.count(("SOL/USDT", "ETH/USDT", "BNB/USDT")), 1)
        self.assertIn(("SOL/USDT", "ETH/USDT"), combos)

    def test_candidate_sweep_summary_orders_metrics(self):
        equity = pd.DataFrame({"equity": [1000.0, 1200.0, 1100.0, 1500.0]})
        trades = pd.DataFrame(
            {
                "pnl": [100.0, -25.0, 50.0],
                "commission": [1.0, 1.0, 1.0],
                "slippage": [2.0, 2.0, 2.0],
                "funding": [0.5, -0.2, 0.1],
            }
        )
        row = portfolio_candidate_sweep.summarize_combo(("SOL/USDT", "ETH/USDT"), trades, equity, years=1)
        self.assertEqual(row["symbols"], "SOL/USDT,ETH/USDT")
        self.assertEqual(row["trades"], 3)
        self.assertEqual(row["final_equity"], 1500.0)
        self.assertGreater(row["cagr_pct"], 0)
        self.assertIn("sharpe", row)
        self.assertIn("sortino", row)
        self.assertIn("calmar", row)

    def test_risk_metrics_equity_and_multiple_testing_summary(self):
        equity = pd.DataFrame({"equity": [1000.0, 1100.0, 1050.0, 1250.0]})
        metrics = risk_metrics.equity_metrics(equity, start_balance=1000.0, timeframe="4h")
        self.assertGreater(metrics["total_return_pct"], 0)
        self.assertGreater(metrics["max_dd_pct"], 0)
        self.assertIn("sharpe", metrics)
        self.assertAlmostEqual(risk_metrics.bonferroni_alpha(0.05, 100), 0.0005)

        sweep = pd.DataFrame({
            "symbols": ["A/USDT,B/USDT", "C/USDT,D/USDT"],
            "cagr_pct": [10.0, 25.0],
        })
        summary = risk_metrics.candidate_sweep_multiple_testing_summary(sweep)
        self.assertEqual(summary["test_count"], 2)
        self.assertEqual(summary["best_symbols"], "C/USDT,D/USDT")
        self.assertEqual(summary["warning"], "multiple_testing_adjustment_required")
        haircut = risk_metrics.multiple_testing_sharpe_haircut(sharpe=1.0, years=3.0, test_count=100)
        self.assertLess(haircut["deflated_sharpe_proxy"], 1.0)
        self.assertEqual(haircut["warning"], "conservative_proxy_not_full_dsr")

        wf = pd.DataFrame({"train_return_pct": [100.0, 80.0], "test_return_pct": [10.0, -5.0]})
        overfit = risk_metrics.walk_forward_overfit_summary(wf)
        self.assertEqual(overfit["folds"], 2)
        self.assertEqual(overfit["severe_degradation_folds"], 2)
        self.assertGreater(overfit["pbo_proxy"], 0)

    def test_risk_adjusted_report_reads_equity_and_sweep(self):
        with tempfile.TemporaryDirectory() as tmp:
            equity_path = Path(tmp) / "equity.csv"
            sweep_path = Path(tmp) / "sweep.csv"
            wf_path = Path(tmp) / "wf.csv"
            pd.DataFrame({"equity": [1000.0, 1100.0, 1050.0]}).to_csv(equity_path, index=False)
            pd.DataFrame({"symbols": ["A/USDT,B/USDT"], "cagr_pct": [10.0]}).to_csv(sweep_path, index=False)
            pd.DataFrame({"train_return_pct": [100.0], "test_return_pct": [20.0]}).to_csv(wf_path, index=False)
            report = risk_adjusted_report.build_report(
                equity_path=str(equity_path),
                sweep_path=str(sweep_path),
                walk_forward_path=str(wf_path),
                timeframe="4h",
            )
            self.assertIn("sharpe", report["equity_metrics"])
            self.assertEqual(report["multiple_testing"]["test_count"], 1)
            self.assertIn("sharpe_haircut", report["overfit_controls"])
            self.assertIn("walk_forward_degradation", report["overfit_controls"])

    def test_pbo_report_flags_oos_underperformance(self):
        matrix = pd.DataFrame({
            "period": [1, 1, 1, 2, 2, 2],
            "candidate": ["A", "B", "C", "A", "B", "C"],
            "selected": [True, False, False, False, True, False],
            "train_score": [3.0, 2.0, 1.0, 1.0, 3.0, 2.0],
            "test_return_pct": [1.0, 10.0, 5.0, 10.0, 1.0, 5.0],
        })
        report = pbo_report.build_pbo_report(matrix)
        self.assertEqual(report["folds"], 2)
        self.assertEqual(report["pbo"], 1.0)
        self.assertLess(report["avg_oos_rank_pct"], 0.5)

    def test_correlation_stress_flags_highly_correlated_pairs(self):
        idx = pd.date_range("2026-01-01", periods=5, freq="4h")
        data_by_symbol = {
            "DOGE/USDT": {"df": pd.DataFrame({"close": [1, 2, 3, 4, 5]}, index=idx)},
            "LINK/USDT": {"df": pd.DataFrame({"close": [2, 4, 6, 8, 10]}, index=idx)},
            "TRX/USDT": {"df": pd.DataFrame({"close": [5, 4, 5, 4, 5]}, index=idx)},
        }
        returns = correlation_stress.symbol_return_frame(data_by_symbol, ["DOGE/USDT", "LINK/USDT", "TRX/USDT"])
        summary = correlation_stress.stress_summary(returns, high_corr_threshold=0.80)
        self.assertGreaterEqual(summary["max_abs_correlation"], 0.80)
        self.assertTrue(summary["high_corr_pairs"])
        self.assertEqual(correlation_stress.suggested_risk_multiplier(0.90), 0.50)
        self.assertEqual(correlation_stress.suggested_risk_multiplier(0.75), 0.75)

    def test_pattern_ablation_restores_config_and_summarizes(self):
        old_enabled = config.PATTERN_RISK_ENABLED
        try:
            config.PATTERN_RISK_ENABLED = True
            with pattern_ablation.temporary_pattern_risk(False):
                self.assertFalse(config.PATTERN_RISK_ENABLED)
            self.assertTrue(config.PATTERN_RISK_ENABLED)

            trades = pd.DataFrame({
                "pnl": [10.0, -2.0],
                "commission": [0.1, 0.1],
                "slippage": [0.2, 0.2],
                "funding": [0.0, 0.0],
            })
            equity = pd.DataFrame({"equity": [1000.0, 1010.0, 1008.0]})
            row = pattern_ablation.summarize_result("unit", trades, equity)
            self.assertEqual(row["scenario"], "unit")
            self.assertEqual(row["trades"], 2)
            self.assertIn("sharpe", row)
        finally:
            config.PATTERN_RISK_ENABLED = old_enabled

    def test_portfolio_param_walk_forward_restores_strategy_config(self):
        old_values = (
            config.DONCHIAN_PERIOD,
            config.DONCHIAN_EXIT,
            config.VOLUME_MULT,
            config.SL_ATR_MULT,
        )
        params = portfolio_param_walk_forward.StrategyParams(15, 8, 1.2, 1.5)
        with portfolio_param_walk_forward.temporary_strategy_params(params):
            self.assertEqual(config.DONCHIAN_PERIOD, 15)
            self.assertEqual(config.DONCHIAN_EXIT, 8)
            self.assertEqual(config.VOLUME_MULT, 1.2)
            self.assertEqual(config.SL_ATR_MULT, 1.5)
        self.assertEqual(
            (
                config.DONCHIAN_PERIOD,
                config.DONCHIAN_EXIT,
                config.VOLUME_MULT,
                config.SL_ATR_MULT,
            ),
            old_values,
        )

    def test_portfolio_param_walk_forward_grid_filters_invalid_exit(self):
        grid = portfolio_param_walk_forward.generate_param_grid()
        self.assertTrue(grid)
        self.assertTrue(all(row.donchian_exit < row.donchian for row in grid))
        self.assertEqual(portfolio_param_walk_forward.generate_param_grid(max_combos=2), grid[:2])

    def test_portfolio_param_walk_forward_selects_risk_capped_profiles(self):
        profiles = portfolio_param_walk_forward.select_profiles(risk_capped=True)
        self.assertEqual(
            [profile["name"] for profile in profiles],
            ["conservative", "balanced", "growth_70_compound"],
        )
        custom = portfolio_param_walk_forward.select_profiles(["balanced"])
        self.assertEqual([profile["name"] for profile in custom], ["balanced"])
        with self.assertRaises(ValueError):
            portfolio_param_walk_forward.select_profiles(["missing_profile"])

    def test_portfolio_cost_stress_adverse_funding_cost(self):
        self.assertEqual(portfolio_cost_stress.adverse_funding_cost(10.0, 2.0), 20.0)
        self.assertEqual(portfolio_cost_stress.adverse_funding_cost(-10.0, 2.0), -5.0)
        with self.assertRaises(ValueError):
            portfolio_cost_stress.adverse_funding_cost(10.0, 0.0)

    def test_portfolio_cost_stress_summary_compounds_folds(self):
        folds = pd.DataFrame({
            "scenario": ["unit", "unit"],
            "test_return_pct": [10.0, -5.0],
            "test_max_dd_peak_pct": [2.0, 3.0],
            "test_trades": [4, 5],
            "fee_mult": [1.0, 1.0],
            "slippage_mult": [2.0, 2.0],
            "funding_cost_mult": [1.0, 1.0],
        })
        summary = portfolio_cost_stress.summarize_folds(folds)
        row = summary.iloc[0].to_dict()
        self.assertEqual(row["positive_periods"], 1)
        self.assertEqual(row["total_trades"], 9)
        self.assertAlmostEqual(row["compounded_oos_final_equity"], 1045.0)

    def test_portfolio_holdout_ranges_use_final_bars(self):
        idx = pd.date_range("2026-01-01", periods=10, freq="4h")
        ranges = portfolio_holdout.holdout_ranges(idx, 3)
        self.assertEqual(ranges["train_start"], idx[0])
        self.assertEqual(ranges["train_end"], idx[6])
        self.assertEqual(ranges["holdout_start"], idx[7])
        self.assertEqual(ranges["holdout_end"], idx[9])
        self.assertEqual(ranges["train_bars"], 7)
        self.assertEqual(ranges["holdout_bars"], 3)
        with self.assertRaises(ValueError):
            portfolio_holdout.holdout_ranges(idx, 10)

    def test_timeframe_sweep_bars_for_days(self):
        self.assertEqual(timeframe_sweep.bars_for_days("1h", 1), 24)
        self.assertEqual(timeframe_sweep.bars_for_days("2h", 1), 12)
        self.assertEqual(timeframe_sweep.bars_for_days("4h", 1), 6)
        self.assertEqual(timeframe_sweep.bars_for_days("1d", 7), 7)

    def test_timeframe_sweep_restores_config(self):
        old_timeframe = config.TIMEFRAME
        old_flow_period = getattr(config, "FLOW_PERIOD", old_timeframe)
        with timeframe_sweep.temporary_timeframe("1h"):
            self.assertEqual(config.TIMEFRAME, "1h")
            self.assertEqual(config.FLOW_PERIOD, "1h")
        self.assertEqual(config.TIMEFRAME, old_timeframe)
        self.assertEqual(config.FLOW_PERIOD, old_flow_period)

    def test_timeframe_sweep_scaled_periods_restore_config(self):
        old_donchian = config.DONCHIAN_PERIOD
        self.assertEqual(timeframe_sweep.scale_factor_to_4h("1h"), 4)
        self.assertEqual(timeframe_sweep.scale_factor_to_4h("2h"), 2)
        with timeframe_sweep.temporary_scaled_periods("1h", enabled=True):
            self.assertEqual(config.DONCHIAN_PERIOD, old_donchian * 4)
        self.assertEqual(config.DONCHIAN_PERIOD, old_donchian)

    def test_timeframe_sweep_unscaled_periods_leave_config_unchanged(self):
        old_donchian = config.DONCHIAN_PERIOD
        with timeframe_sweep.temporary_scaled_periods("1h", enabled=False):
            self.assertEqual(config.DONCHIAN_PERIOD, old_donchian)
        self.assertEqual(config.DONCHIAN_PERIOD, old_donchian)


if __name__ == "__main__":
    unittest.main()
