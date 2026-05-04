from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import config
import data
import runtime_guards


def build_preflight(*, include_files: bool = True) -> dict[str, Any]:
    checks = [
        _check("testnet_disabled_for_live", not bool(getattr(config, "TESTNET", True)), "TESTNET must be False for live."),
        _check("live_approved", bool(getattr(config, "LIVE_TRADING_APPROVED", False)), "LIVE_TRADING_APPROVED must be True."),
    ]

    profile = data.live_profile_status()
    checks.append(_check("live_profile", bool(profile.get("ok")), profile.get("reason") or "", profile))

    stream = data.user_data_stream_status()
    checks.append(_check("user_data_stream", bool(stream.get("ok")), stream.get("reason") or "", stream))

    disabled = runtime_guards.trading_disabled()
    checks.append(_check("trading_not_disabled", not disabled, "trading disabled flag exists"))

    checks.append(_check(
        "liquidation_guard_enabled",
        bool(getattr(config, "LIQUIDATION_GUARD_ENABLED", False)),
        "LIQUIDATION_GUARD_ENABLED must be True for live.",
    ))
    checks.append(_check(
        "protections_enabled",
        bool(getattr(config, "PROTECTIONS_ENABLED", False)),
        "PROTECTIONS_ENABLED must be True for live.",
    ))

    if include_files:
        checks.append(_check(
            "api_key_runbook_exists",
            Path("docs/API_KEY_SECURITY_RUNBOOK_2026_05_01.md").exists(),
            "API key security runbook missing.",
        ))
        checks.append(_check(
            "user_stream_runner_doc_exists",
            Path("docs/USER_STREAM_RUNNER_2026_05_04.md").exists(),
            "User stream runner decision doc missing.",
        ))

    ok = all(row["ok"] for row in checks)
    return {
        "ok": ok,
        "mode": "live_preflight",
        "checks": checks,
        "summary": "go_live_allowed" if ok else "go_live_blocked",
    }


def _check(name: str, ok: bool, reason: str = "", details: dict[str, Any] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"name": name, "ok": bool(ok)}
    if reason and not ok:
        row["reason"] = reason
    if details is not None:
        row["details"] = details
    return row


def print_text(report: dict[str, Any]) -> None:
    print("=== GO LIVE PREFLIGHT ===")
    print(f"summary: {report['summary']}")
    for row in report["checks"]:
        status = "OK" if row["ok"] else "BLOCK"
        reason = f" | {row.get('reason')}" if row.get("reason") else ""
        print(f"{status:<5} {row['name']}{reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed live trading preflight.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_preflight()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
