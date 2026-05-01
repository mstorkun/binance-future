import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import ccxt
import pandas as pd

import config
import bias_audit
import exit_ladder
import flow_data
import order_manager
import paper_runtime
import pair_universe
import paper_runner
import paper_report
import portfolio_candidate_sweep
import protections
import risk
import timeframe_sweep
import trade_executor
import twap_execution
import walk_forward


class FakeExchange:
    def __init__(self):
        self.created_orders = []

    def cancel_all_orders(self, symbol):
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


class SafetyTests(unittest.TestCase):
    def test_market_close_still_runs_when_cancel_fails(self):
        old_symbol = config.SYMBOL
        try:
            config.SYMBOL = "SOL/USDT"
            exchange = FakeExchange()
            ok = order_manager.close_position_market(exchange, "long", 1.25)
            self.assertTrue(ok)
            self.assertEqual(len(exchange.created_orders), 1)
            self.assertEqual(exchange.created_orders[0]["side"], "sell")
            self.assertTrue(exchange.created_orders[0]["params"]["reduceOnly"])
        finally:
            config.SYMBOL = old_symbol

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

    def test_paper_runner_lock_blocks_second_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "paper.lock"
            with paper_runner.PaperRunnerLock(lock_path):
                with self.assertRaises(RuntimeError):
                    with paper_runner.PaperRunnerLock(lock_path):
                        pass
            self.assertFalse(lock_path.exists())

    def test_paper_csv_append_expands_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "paper.csv"
            paper_runner._append_csv(str(csv_path), [{"symbol": "SOL/USDT", "action": "no_signal"}])
            paper_runner._append_csv(str(csv_path), [{"symbol": "ETH/USDT", "action": "no_signal", "flow_fresh": True}])
            rows = list(pd.read_csv(csv_path).to_dict("records"))
            self.assertIn("flow_fresh", pd.read_csv(csv_path).columns)
            self.assertEqual(rows[-1]["flow_fresh"], True)

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

                report = paper_report.build_report(decision_limit=10)
                self.assertEqual(report["heartbeat"]["status"], "ok")
                self.assertEqual(report["recent"]["actions"]["no_signal"], 1)
                self.assertEqual(report["recent"]["actions"]["skip"], 1)
                self.assertEqual(report["recent"]["skips"]["risk_block"], 1)
                self.assertEqual(report["warnings"], [])
        finally:
            config.SYMBOLS = old_symbols
            config.PAPER_HEARTBEAT_FILE = old_heartbeat
            config.PAPER_DECISIONS_CSV = old_decisions
            config.PAPER_EQUITY_CSV = old_equity
            config.PAPER_TRADES_CSV = old_trades
            config.PAPER_ERRORS_CSV = old_errors
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
