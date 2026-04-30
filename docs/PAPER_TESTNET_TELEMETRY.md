# Paper And Testnet Telemetry

Date: 2026-05-01

This is the live-readiness layer before any real deployment.

## Paper Runner

Run one decision cycle:

```bash
python paper_runner.py --once
```

Reset the virtual account:

```bash
python paper_runner.py --once --reset
```

Run continuously:

```bash
python paper_runner.py --loop --interval-minutes 60
```

The paper runner sends no orders. It writes local runtime files:

- `paper_state.json`
- `paper_decisions.csv`
- `paper_trades.csv`
- `paper_equity.csv`

These files are ignored by git.

## What Gets Logged

For every symbol and cycle:

- current signal or no-signal state
- ADX, RSI, ATR, regime, daily/weekly trend
- candlestick pattern scores and bias
- futures flow fields: taker buy ratio, top trader ratio, OI change, funding
- calendar/news risk reasons
- effective risk percent
- order-book guard result and reason
- paper open/hold/skip/close actions

## Testnet Fill Probe

For real fill/slippage measurement on Binance Futures testnet:

```bash
python testnet_fill_probe.py --symbol SOL/USDT --side long --approve-testnet-fill
```

Safety gates:

- refuses to run unless `config.TESTNET = True`
- requires API keys
- requires the explicit `--approve-testnet-fill` flag
- immediately closes the tiny testnet position

Output:

- `testnet_fill_probe.csv`

## Promotion Gate

Do not enable live trading until paper/testnet logs show:

- no repeated order-book guard failures
- no unexpected risk multipliers
- flow data is available for the traded symbols
- testnet fill slippage is inside the modeled slippage budget
- paper exits match the backtest execution assumptions closely enough

## Smoke Test

Latest local smoke test:

- `python paper_runner.py --once --reset`
- result: `equity=1000.00`, `wallet=1000.00`, `open=0`, `decisions=3`, `closed=0`
- `python testnet_fill_probe.py --symbol SOL/USDT`
- result: refused to send an order because `--approve-testnet-fill` was not supplied
