"""Example runtime notes.

Do not put API keys in Python files. Use `.env` or environment variables:

BINANCE_API_KEY=...
BINANCE_API_SECRET=...

Trading parameters live in `config.py` for research/testnet defaults. Live mode
must stay blocked until `go_live_preflight.py` passes and the API key runbook is
completed.
"""

TESTNET = True
LIVE_TRADING_APPROVED = False
