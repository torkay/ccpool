# ccpool

`ccpool` is an account-rotation wrapper for Anthropic's `claude` CLI.

It targets users running multiple Anthropic subscriptions (any combination of Pro, Max, and Team) and picks which account to use per `claude` invocation, based on real-time usage data from Anthropic's `/api/oauth/usage` endpoint. Selection is tiered: usage-aware first, [`caam`](https://github.com/Dicklesworthstone/coding_agent_account_manager)'s local heuristic if the endpoint is unreachable, deterministic round-robin if both fail.

No background daemons. Ticks via launchd interval (macOS) or systemd-user timer (Linux), with a crontab fallback. Built on top of `caam` for per-account isolation; doesn't replace it.

![statusline modes](docs/img/statusline.gif)

## Install

```bash
# Homebrew (macOS)
brew tap torkay/ccpool
brew install ccpool

# pipx (macOS + Linux)
pipx install ccpool

# curl-bash
curl -fsSL https://raw.githubusercontent.com/torkay/ccpool/main/install/install.sh | bash
```

`caam` must be on `$PATH` first (`brew install dicklesworthstone/tap/caam` or `go install github.com/Dicklesworthstone/coding_agent_account_manager/cmd/caam@latest`).

## Configure

`ccpool setup` registers profiles. Each one gets its own `caam`-isolated home and its own long-lived OAuth token. Tokens land in the platform keychain (macOS Keychain, Linux libsecret) or in a `tokens.env` 0600 file as fallback.

```
$ ccpool setup
═══════════════════════════════════════════════════════════════════
  ccpool setup
═══════════════════════════════════════════════════════════════════
Wires up Anthropic account rotation for the claude CLI.

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
```

Once set up, `claude` is shadowed by `ccpool` in your shell-rc. Existing scripts and `claude ...` invocations route through the picker without changes.

## Picker

Three tiers, ordered:

1. **Usage-aware.** `/api/oauth/usage` is queried per profile (Anthropic caches the response for 5 min). The profile with the lowest combined 5-hour and 7-day utilisation is selected.
2. **`caam` local.** If the usage endpoint is unreachable, fall back to `caam`'s heuristic (token age, request counts, recent failures).
3. **Round-robin.** Last resort. Deterministic, never blocks.

Hard saturation guard: if every profile is above `picker.hard_threshold_pct` (default 95) on either window, ccpool refuses to spawn rather than letting a request 429 mid-turn. State is exposed via `ccpool usage` and `ccpool statusline`.

![usage table](docs/img/usage.gif)

## Statusline

`ccpool statusline` emits one-line JSON for prompt integration. Three text variants:

```
$ ccpool statusline --short
🟢 personal 42% / 71%

$ ccpool statusline --no-color
OK personal 42% / 71%

$ ccpool statusline --format='{marker} {profile} {five}/{seven}'
OK personal 42%/72%
```

Format placeholders: `{emoji}` `{marker}` `{profile}` `{five}` `{seven}` `{saturated}` `{degraded}`. See [docs/integrations.md](docs/integrations.md) for Starship, p10k, oh-my-zsh, tmux, and bash recipes.

## Token storage

Pluggable. Default backend is the platform keychain (`security` on macOS, `secret-tool` via libsecret on Linux). The `tokens.env` 0600 file fallback exists because of Apple Keychain ACL bug #20553, which makes namespaced credentials lose readability after a reboot. Set `CCPOOL_FORCE_ENV_STORAGE=1` to skip the keychain entirely.

Tokens are issued by Claude itself (`claude setup-token`) and rotate on a watchdog cadence; profile names and email addresses stay local.

## Status

Pre-1.0. The CLI surface and config schema may still shift. v1.0.0 ships when the matrix is green on macOS 13/14 and Ubuntu 22/24.

## Documentation

- [INSTALL.md](docs/INSTALL.md), every install path with verify steps
- [REFERENCE.md](docs/REFERENCE.md), every subcommand and config key
- [ARCHITECTURE.md](docs/ARCHITECTURE.md), module roles and decisions
- [THREAT_MODEL.md](docs/THREAT_MODEL.md), security stance, what's in and out of scope
- [PROVIDERS.md](docs/PROVIDERS.md), Anthropic via `claude` (full); `codex` and `gemini` planned
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md), symptoms to fixes
- [COMPATIBILITY.md](docs/COMPATIBILITY.md), version matrix
- [docs/integrations.md](docs/integrations.md), shell prompt recipes
- [docs/captures/](docs/captures/), VHS tape files for higher-fidelity terminal recordings

## License

MIT. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.
