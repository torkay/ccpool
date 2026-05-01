# ccpool

> Smart Claude Max account rotation. Zero daemons. Zero lock-in.

`ccpool` (binary: `ccpool`) routes your `claude` invocations across multiple Claude Max accounts so you never hit the per-account 5-hour or 7-day cap. It uses Anthropic's own `/api/oauth/usage` endpoint as ground truth and falls back to local heuristics when the endpoint is unreachable.

Built on top of [`caam`](https://github.com/Dicklesworthstone/coding_agent_account_manager) for per-account isolation. No background daemons; runs as a launchd / systemd-user interval job.

## Status

**Pre-1.0.** API and config schema may change. v1.0.0 ships when the test matrix is green on macos-13/14 and ubuntu-22/24.

## Install (preview)

```bash
# Homebrew (macOS, recommended)
brew tap torkay/ccpool
brew install ccpool

# pipx (Linux + macOS)
pipx install ccpool

# curl-bash one-liner
curl -fsSL https://raw.githubusercontent.com/torkay/ccpool/main/install/install.sh | bash
```

After install:

```bash
ccpool setup    # interactive bootstrap; asks for accounts, opens browser for OAuth
ccpool usage    # live ground-truth utilization
ccpool doctor   # health check
```

Day-to-day, `ccpool setup` aliases `claude` → `ccpool` so you keep your muscle memory.

## 30-second demo

```bash
$ ccpool setup
═══════════════════════════════════════════════════════════════════
  ccpool setup
═══════════════════════════════════════════════════════════════════
Wires up smart Claude Max account rotation.

  Profile 1 name: personal
  Profile 1 email: you@example.com
  → opening Claude sign-in. Use account: you@example.com
  ✓ signed in (account verified)
  → Issuing long-lived token for you@example.com
  ✓ token stored (keychain)

  Profile 2 name: secondary
  Profile 2 email: you+work@example.com
  ✓ signed in · ✓ token stored (keychain)

Automation
  ✓ rotation watcher
  ✓ daily watchdog
  ✓ shell-rc managed-block written

All set. From a new terminal, just type:  ccpool

$ ccpool statusline --short
🟢 personal 42% / 71%

$ ccpool usage --json | jq '.profiles[] | {name, five_hour_pct, seven_day_pct}'
{"name":"personal","five_hour_pct":42.0,"seven_day_pct":71.5}
{"name":"secondary","five_hour_pct":18.3,"seven_day_pct":34.0}
```

## Features

- **Smart picker, 3 tiers**: usage-aware (Anthropic `/api/oauth/usage`) → caam smart (local heuristic) → deterministic round-robin
- **Hard saturation guard**: refuses to spawn when *all* accounts cross 95% rather than letting requests 429
- **Token rotation**: long-lived OAuth tokens via `claude setup-token`, age-tracked; `ccpool rotate` re-issues
- **Storage abstraction**: macOS Keychain / libsecret / `tokens.env` 0600 fallback — works around Apple keychain ACL bug #20553
- **Doctor with auto-fix**: severity-rated findings, idempotent fixes for common breakage
- **Status line for prompts**: `ccpool statusline` emits one-line JSON for Starship / p10k / oh-my-zsh
- **No daemons**: tick-only via launchd interval job (macOS) or systemd-user timer (Linux); crontab fallback

## Why?

If you've got two Claude Max subscriptions you're already paying for, you're throwing away half your inference budget when one account caps out and the other sits idle. `ccpool` keeps them balanced.

## Documentation

- [INSTALL.md](docs/INSTALL.md) — every install path with verify steps
- [REFERENCE.md](docs/REFERENCE.md) — every subcommand and config key
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — module roles and decision rationale
- [THREAT_MODEL.md](docs/THREAT_MODEL.md) — security stance, what's in/out of scope
- [PROVIDERS.md](docs/PROVIDERS.md) — claude (full), codex/gemini (planned)
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — symptoms → fixes
- [COMPATIBILITY.md](docs/COMPATIBILITY.md) — version matrix

## License

MIT — see [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.
