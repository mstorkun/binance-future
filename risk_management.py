"""
Deprecated risk helper.

This module used a legacy margin * leverage formula that is not compatible with
the current ATR-stop sizing model. Keep the file as a visible quarantine marker
so old imports fail loudly instead of silently reintroducing stale sizing.
"""


def calculate_position_size(*args, **kwargs):
    raise RuntimeError(
        "risk_management.py is deprecated. Use risk.position_size() and the "
        "portfolio risk path instead."
    )
