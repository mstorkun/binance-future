from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

import config


def trading_disabled_path(path: str | Path | None = None) -> Path:
    return Path(path or getattr(config, "TRADING_DISABLED_FLAG", "trading_disabled.flag"))


def trading_disabled(path: str | Path | None = None) -> bool:
    return trading_disabled_path(path).exists()


def disable_trading(reason: str, path: str | Path | None = None) -> Path:
    target = trading_disabled_path(path)
    if target.parent and str(target.parent) != ".":
        target.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        f"disabled_at_utc={pd.Timestamp.now(tz='UTC').isoformat()}\n"
        f"reason={reason.strip() or 'manual'}\n"
    )
    with target.open("w", encoding="utf-8") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    return target


def enable_trading(path: str | Path | None = None) -> None:
    target = trading_disabled_path(path)
    if target.exists():
        target.unlink()


def assert_trading_enabled(path: str | Path | None = None) -> None:
    target = trading_disabled_path(path)
    if target.exists():
        raise RuntimeError(f"Trading is disabled by flag: {target}")
