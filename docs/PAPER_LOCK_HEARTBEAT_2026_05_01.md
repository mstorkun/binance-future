# Paper Lock Heartbeat 2026-05-01

Status: closes the P1 stale paper-lock heartbeat item.

## Why

The paper runner lock prevented duplicate writers, but the lock file was only
written at startup. A long-running paper process could leave an old lock mtime,
making restart diagnostics ambiguous and increasing the chance of stale-lock
handling removing a live runner's lock.

## Change

- `PaperRunnerLock` now writes `created_at` and `updated_at`.
- `PaperRunnerLock.refresh()` rewrites and fsyncs the lock file.
- The main loop refreshes the lock:
  - after a successful telemetry cycle,
  - before normal sleep,
  - before error sleep.
- Tests verify that refresh updates both the JSON heartbeat timestamp and file
  mtime while preserving `created_at`.

## Verification

- `python -m py_compile paper_runner.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `85 passed, 3 subtests passed`
- `python -m pytest -q` -> `85 passed, 3 subtests passed`
