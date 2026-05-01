# API Key Security Runbook 2026-05-01

Status: closes P0 #36 as an operating runbook. This does not approve live
trading.

Sources checked on 2026-05-01:

- Binance API key creation FAQ:
  <https://www.binance.com/en/support/faq/how-to-create-api-keys-on-binance-360002502072>
- Binance Academy API key security:
  <https://www.binance.com/en/academy/articles/what-are-api-keys-and-security-types>
- Binance Developer Community `-2015` triage:
  <https://dev.binance.vision/t/why-do-i-see-this-error-invalid-api-key-ip-or-permissions-for-action/93>

## Required Live-Key Shape

Use one dedicated API key for this bot only.

Required:

- Enable Reading.
- Enable Futures trading for USD-M Futures.
- Restrict access to trusted IPv4 addresses only.
- Whitelist only the bot host's static outbound IPv4.
- Keep `BINANCE_API_KEY` and `BINANCE_API_SECRET` in environment variables or an
  untracked `.env` file.

Forbidden:

- Do not enable withdrawals.
- Do not enable Universal Transfer.
- Do not enable Spot/Margin trading unless a future strategy explicitly needs it
  and a new review approves it.
- Do not share this API key with TradingView, copy-trading services, dashboards,
  notebooks, or another bot.
- Do not commit API keys, `.env`, runtime logs, screenshots showing secrets, or
  exported key files.

Preferred if Binance UI supports it:

- Symbol whitelist: only `DOGEUSDT`, `LINKUSDT`, and `TRXUSDT` for the current
  candidate portfolio.
- Self-generated Ed25519 key with a passphrase for production operations.

## Host And IP Rule

Live trading must run from a VPS or server with a stable static outbound IPv4.
Home internet is not acceptable for live keys because dynamic IP changes can
break trading permissions or tempt broad IP access.

Before creating or editing the live key, confirm the server's public IPv4 from
the same machine that will run the bot:

```powershell
(Invoke-RestMethod -Uri "https://api.ipify.org").Trim()
```

Add exactly that IPv4 under Binance API Management's trusted-IP restriction for
the bot key.

If the server IP changes:

1. Stop the bot.
2. Run the dry-run kill switch:
   `python emergency_kill_switch.py --json`
3. If positions/orders exist, handle them manually or run the explicitly
   approved execute command.
4. Update the Binance trusted-IP list.
5. Run `python ops_status.py --exchange --json`.
6. Restart only after account safety checks are clean.

## Testnet/Demo Key Rule

Testnet/demo keys must stay separate from live keys. A production key on testnet,
or a testnet key on production, can raise `-2015 Invalid API-key, IP, or
permissions for action`.

For this repo:

- `config.TESTNET=True` remains the default.
- `config.LIVE_TRADING_APPROVED=False` remains the default.
- Testnet probes must use explicit approval flags already present in the probe
  scripts.

## Go-Live Checklist

Before any live key is used:

1. Confirm `git status` has no secret-bearing files staged or modified.
2. Confirm `.env` is ignored and not tracked.
3. Confirm Binance account has Futures enabled before creating the key. If the
   key was created before Futures was enabled, recreate the key.
4. Confirm Portfolio Margin is not interfering with Futures permission for this
   bot profile.
5. Confirm the API key has Reading + Futures trading only.
6. Confirm Withdrawals and Universal Transfer are disabled.
7. Confirm trusted-IP restriction contains only the bot server IPv4.
8. Confirm the key label includes environment and host, for example:
   `binance-bot-live-vps-YYYYMMDD`.
9. Confirm `python ops_status.py --exchange --json` passes.
10. Confirm `python emergency_kill_switch.py --json` can read planned emergency
    actions without error.

## Rotation And Compromise

Rotate the live bot key monthly or sooner after any host migration, operator
change, suspected leak, or abnormal Binance security notification.

If compromise is suspected:

1. Disable/delete the key in Binance immediately.
2. Run `python emergency_kill_switch.py --json` from the trusted host if the key
   still works and emergency action is needed.
3. Manually inspect open orders and positions in Binance UI.
4. Create a new key only after the host and repo are checked.
5. Record the incident in a dated doc under `docs/`.

## Common `-2015` Causes

When Binance returns `Invalid API-key, IP, or permissions for action`, check:

- wrong API key or missing `X-MBX-APIKEY` header,
- current server IP not in the trusted-IP list,
- IPv6 path being used instead of the whitelisted IPv4,
- missing permission for the endpoint,
- production key used against testnet or testnet key used against production,
- Futures key created before Futures account activation.

Do not broaden permissions as a first fix. Identify the exact failed endpoint
and fix the narrow cause.
