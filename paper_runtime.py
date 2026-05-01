"""Runtime context helpers for isolated paper/shadow runs."""
from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import Iterator

import pandas as pd

import config


PAPER_FILE_ATTRS = [
    "PAPER_STATE_FILE",
    "PAPER_DECISIONS_CSV",
    "PAPER_TRADES_CSV",
    "PAPER_EQUITY_CSV",
    "PAPER_ERRORS_CSV",
    "PAPER_HEARTBEAT_FILE",
    "PAPER_LOCK_FILE",
]

SCALABLE_PERIOD_FIELDS = [
    "EMA_FAST",
    "EMA_SLOW",
    "ADX_PERIOD",
    "RSI_PERIOD",
    "ATR_PERIOD",
    "DONCHIAN_PERIOD",
    "DONCHIAN_EXIT",
    "VOLUME_MA_PERIOD",
    "VOLUME_PROFILE_LOOKBACK",
    "VOLUME_PROFILE_MIN_BARS",
    "PATTERN_SWEEP_LOOKBACK",
    "WARMUP_BARS",
]


def sanitize_run_tag(tag: str | None) -> str:
    if not tag:
        return ""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", tag.strip()).strip("._-")
    if not cleaned:
        raise ValueError("paper run tag is empty after sanitization")
    return cleaned[:64]


def tagged_runtime_path(path: str | Path, tag: str) -> str:
    p = Path(path)
    if not tag:
        return str(p)
    name = p.name
    if name.startswith("paper_"):
        tagged_name = f"paper_{tag}_{name[len('paper_'):]}"
    else:
        tagged_name = f"{p.stem}_{tag}{p.suffix}"
    return str(p.with_name(tagged_name))


def timeframe_to_timedelta(timeframe: str) -> pd.Timedelta:
    match = re.fullmatch(r"(\d+)([mhdw])", timeframe.strip().lower())
    if not match:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "m":
        return pd.Timedelta(minutes=value)
    if unit == "h":
        return pd.Timedelta(hours=value)
    if unit == "d":
        return pd.Timedelta(days=value)
    if unit == "w":
        return pd.Timedelta(weeks=value)
    raise ValueError(timeframe)


def scale_factor_to_4h(timeframe: str) -> float:
    return pd.Timedelta(hours=4).total_seconds() / timeframe_to_timedelta(timeframe).total_seconds()


@contextlib.contextmanager
def temporary_paper_runtime(
    *,
    tag: str | None = None,
    timeframe: str | None = None,
    scale_lookbacks: bool = False,
) -> Iterator[None]:
    """Temporarily isolate paper files and optional timeframe settings."""
    run_tag = sanitize_run_tag(tag)
    attrs_to_save = set(PAPER_FILE_ATTRS + SCALABLE_PERIOD_FIELDS + [
        "TIMEFRAME",
        "FLOW_PERIOD",
        "PAPER_RUN_TAG",
        "PAPER_SCALED_LOOKBACKS",
    ])
    saved = {attr: getattr(config, attr) for attr in attrs_to_save if hasattr(config, attr)}
    try:
        if run_tag:
            for attr in PAPER_FILE_ATTRS:
                if hasattr(config, attr):
                    setattr(config, attr, tagged_runtime_path(getattr(config, attr), run_tag))
        config.PAPER_RUN_TAG = run_tag or "default"
        config.PAPER_SCALED_LOOKBACKS = bool(scale_lookbacks)

        if timeframe:
            config.TIMEFRAME = timeframe
            config.FLOW_PERIOD = timeframe

        if scale_lookbacks:
            factor = scale_factor_to_4h(getattr(config, "TIMEFRAME"))
            for field in SCALABLE_PERIOD_FIELDS:
                if hasattr(config, field):
                    value = float(saved.get(field, getattr(config, field)))
                    setattr(config, field, max(2, int(round(value * factor))))
        yield
    finally:
        for attr in attrs_to_save:
            if attr in saved:
                setattr(config, attr, saved[attr])
            elif hasattr(config, attr):
                delattr(config, attr)
