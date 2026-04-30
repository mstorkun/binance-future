# Claude Code Notes

Token-saving rules for this repo:

- **Never read** large CSV outputs (`*_results.csv`); use `head` via Bash if needed.
- **Never read** `bot.log`, `.env`, `__pycache__/`, `.venv/`.
- **Use `Grep`/`Glob`** for search instead of bulk Read.
- **Run scripts** (`python backtest.py` etc.) and read **only the tail** of stdout.
- For large refactors, split tasks into 2-3 smaller turns; run `/compact` between.
- Output style suggestion: switch Claude Code to **Concise** or **Laser**.

Repo overview: see [README.md](README.md). Strategy and architecture: [docs/](docs/).

Before continuing project work, read [AI_MEMORY.md](AI_MEMORY.md) for the latest
repo-local handoff, user priorities, validation state, and known dirty files.
