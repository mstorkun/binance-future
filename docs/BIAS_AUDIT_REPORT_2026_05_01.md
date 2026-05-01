# Bias Audit Report 2026-05-01

Status: closes the P1 "bias audit artifacts not committed" item for the active
candidate symbols.

## Command

```bash
python bias_audit_report.py --symbols DOGE/USDT LINK/USDT TRX/USDT --years 1 --sample-step 96 --fail-on-issue
```

## Result

The committed JSON artifact is
[BIAS_AUDIT_REPORT_2026_05_01.json](BIAS_AUDIT_REPORT_2026_05_01.json).

| Symbol | Timeframe | Years | Rows | Sample step | Issues |
|---|---|---:|---:|---:|---:|
| DOGE/USDT | 4h | 1 | 2190 | 96 | 0 |
| LINK/USDT | 4h | 1 | 2190 | 96 | 0 |
| TRX/USDT | 4h | 1 | 2190 | 96 | 0 |

Checked columns:

- `atr`
- `rsi`
- `adx`
- `donchian_high`
- `donchian_low`
- `donchian_exit_high`
- `donchian_exit_low`
- `volume_ma`
- `regime`
- `pattern_score_long`
- `pattern_score_short`
- `pattern_bias`

## Interpretation

This reduces lookahead/recursive-indicator risk for the current feature set. It
does not prove strategy edge and does not approve live trading. Re-run this
report after indicator, pattern, timeframe, or data-loading changes.

## Verification

- `python -m py_compile bias_audit_report.py tests\test_safety.py`
- `python -m pytest tests\test_safety.py -q` -> `86 passed, 3 subtests passed`
- `python -m pytest -q` -> `86 passed, 3 subtests passed`
- `python bias_audit_report.py --symbols DOGE/USDT LINK/USDT TRX/USDT --years 1 --sample-step 96 --fail-on-issue`
