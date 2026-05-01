# Reference

Complete reference for every `ccpool` subcommand, every flag, every config key, and every exit code.

For a friendlier entry, see [INSTALL.md](INSTALL.md) and [README.md](../README.md). For internals, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Subcommands

`ccpool <subcommand> [args...]`. With no subcommand, `ccpool` runs `claude` directly with rotation + token injection. Anything that doesn't match a known subcommand also falls through to `claude` (so `ccpool --version` runs `claude --version`).

### `ccpool setup`

Interactive bootstrap. Asks for accounts, opens the browser for OAuth, stores per-account tokens, wires up shell rc + scheduled jobs.

```bash
ccpool setup
```

Re-run any time. Skips anything already done. If `ccpool migrate detect` finds v0 (personal) state, it offers migration before continuing — see [§ migrate](#ccpool-migrate).

**What it does, step-by-step:**

1. Verifies `caam` and `claude` are on `$PATH` (exits early if not).
2. Detects v0 substrate (legacy personal-substrate profile names, etc.) and prompts for migration if found.
3. If `config.toml` doesn't exist or has no profiles, prompts interactively for profile name + email pairs (≥2 required; ≥3 supported).
4. For each profile, in order:
   - Ensures `caam` profile dir exists.
   - Opens `claude auth login --claudeai --email <email>` in a browser.
   - Detects same-account collision (two profiles signed into the same Claude account); aborts with remediation if detected.
   - Issues a long-lived token via `claude setup-token`; stores in keychain (or `tokens.env` 0600 fallback).
5. Installs the rotation watcher + daily watchdog as launchd plists (macOS) or systemd-user units (Linux). Falls back to crontab if systemd-user is unavailable.
6. Writes the managed shell-rc block (zsh + bash + fish, whichever exist).
7. Runs `ccpool usage` as a smoke test.

**Exit codes:** 0 on success; 1 on any preflight failure (caam/claude missing, same-account detection, etc.).

### `ccpool status [--json]`

Health dashboard for all configured profiles.

| Flag | Meaning |
|---|---|
| `--json` | machine-readable output |

Without `--json`, prints a human table with profile names, token ages, schedule state, and most recent usage snapshot.

**Exit codes:** 0 if any profile is healthy; non-zero if no usable profile (rotation cannot operate).

### `ccpool doctor [--fix] [--json]`

Diagnose problems and optionally auto-fix them.

| Flag | Meaning |
|---|---|
| `--fix` | apply auto-fix paths where available |
| `--json` | machine-readable output |

**Finding codes** (stable across releases — used by `ccpool recover` and `TROUBLESHOOTING.md`):

| Code | Severity | Meaning | Auto-fix |
|---|---|---|---|
| `caam_missing` | CRITICAL | `caam` not on `$PATH` | print install hint |
| `claude_missing` | CRITICAL | `claude` not on `$PATH` | print install hint |
| `no_config` | HIGH | `config.toml` not found | `ccpool setup` |
| `caam_version_too_old` | HIGH | caam below pinned minimum | print upgrade |
| `claude_version_too_old` | MEDIUM | claude below tested version | print upgrade |
| `no_profiles` | HIGH | config has 0 profiles | `ccpool setup` |
| `single_profile` | MEDIUM | only 1 profile (rotation needs 2+) | `ccpool setup` |
| `keychain_locked` | HIGH | `security` cannot read keychain | interactive unlock |
| `keychain_acl_corrupted` | HIGH | Apple bug #20553 | `ccpool recover --rebuild-keychain` |
| `secrets_backend_inconsistent` | LOW | mixed env + keychain storage | print summary |
| `plist_not_loaded` | MEDIUM | watcher/watchdog missing from launchd | `ccpool doctor --fix` |
| `plist_label_drift` | MEDIUM | label doesn't match `cfg.repo_owner` | `ccpool doctor --fix` |
| `systemd_unit_missing` | MEDIUM | Linux unit file gone | `ccpool doctor --fix` |
| `zshrc_block_drift` | LOW | rc file managed-block changed externally | `ccpool doctor --fix` |
| `oauth_endpoint_410` | CRITICAL | `/api/oauth/usage` deprecated by Anthropic | activate Plan-B |
| `config_schema_version_drift` | HIGH | `cfg.meta.schema_version` mismatch | `ccpool migrate` |
| `same_account_detected` | HIGH | runtime: two profiles share the same Claude account | print remedy (no auto-fix) |
| `profile_stub` | MEDIUM | caam dir exists but `.credentials.json` missing | suggest re-`ccpool setup` |
| `token_age_warn` | LOW | token > 330 days old | suggest `ccpool rotate <profile>` |
| `token_age_critical` | HIGH | token > 360 days old | `ccpool rotate <profile>` |

**Exit codes:** 0 if no findings ≥ HIGH; 1 if any HIGH; 2 if any CRITICAL.

### `ccpool rotate [<profile>|all]`

Re-issue and store a new long-lived OAuth token. Interactive — opens the browser for `claude setup-token`.

```bash
ccpool rotate            # rotate all profiles, in turn
ccpool rotate alpha      # rotate one profile
ccpool rotate all        # explicit; same as no-arg
```

**Exit codes:** 0 if at least one profile rotated successfully; 1 otherwise.

### `ccpool recover`

Maintenance reset. Prunes caam backups, clears `degraded`/`saturated` flags, re-stages launchd/systemd schedules.

| Flag | Meaning |
|---|---|
| `--rebuild-keychain` | wipe and re-add keychain entries from `tokens.env` mirror (Apple bug #20553) |
| `--prune-only` | just prune caam backups; skip everything else |

**Exit codes:** 0 on clean recovery; non-zero if any step fails (output explains).

### `ccpool logs [-n N]`

Tail the rotation watcher's NDJSON event log.

```bash
ccpool logs              # last 50 events
ccpool logs -n 200       # last 200
ccpool logs -n 0         # follow (tail -f equivalent)
```

Events live at `$XDG_DATA_HOME/ccpool/watcher.ndjson`. Each line is a JSON object with `ts`, `event`, `profile`, and optional `data`.

### `ccpool pick [--token] [--json]`

Debug: print the env block the next subagent spawn would inherit.

| Flag | Meaning |
|---|---|
| `--token` | include `CLAUDE_CODE_OAUTH_TOKEN` (token printed in plaintext — be careful) |
| `--json` | structured output (default is `KEY=VALUE` lines suitable for `eval`) |

This is the contract for spawn-substrate integration ([ADR](ADRs/) — `pick` is the documented integration point; consumers run `eval "$(ccpool pick)"` to inherit the env into a child process).

### `ccpool usage [--json]`

Per-account 5-hour and 7-day utilization, fetched from Anthropic's `/api/oauth/usage` endpoint.

| Flag | Meaning |
|---|---|
| `--json` | machine-readable |

When the endpoint is unreachable, falls back to local `caam_blocks` JSONL parsing (see [ADR-0007](ADRs/0007-oauth-usage-undocumented-endpoint.md)).

**Exit codes:** 0 always — usage failures are surfaced through `ccpool doctor`, not as exit codes here.

### `ccpool statusline [--short]`

One-line JSON for prompt integrations (Starship, Powerlevel10k, oh-my-zsh).

```bash
$ ccpool statusline
{"version":1,"profile":"personal","five_hour_pct":42.0,"seven_day_pct":71.5,"saturated":false,"degraded":false,"emoji":"🟢"}

$ ccpool statusline --short
🟢 personal 42% / 72%
```

| Flag | Meaning |
|---|---|
| `--short` | human-readable single-line (emoji + profile + percentages) |

Starship integration:

```toml
[custom.ccpool]
command = "ccpool statusline --short"
when    = "command -v ccpool"
format  = "[$output]($style) "
style   = "bold green"
```

### `ccpool migrate {detect|plan|apply}`

Migrate from v0 (personal) substrate to v1 ccpool config.

| Subcommand | Effect |
|---|---|
| `detect` | print JSON: `{"detected": bool, "signals": [...]}` |
| `plan` | dry-run: show would-write `config.toml` and label changes |
| `apply` | atomic migration: write config, re-stage launchd jobs, update shell-rc |

`detect` is read-only and safe in any state.

**Exit codes:** 0 if no v0 detected (or successful migration); 1 if migration aborts.

### `ccpool enable | disable`

Master kill-switch.

```bash
ccpool disable        # writes $XDG_DATA_HOME/ccpool/disabled; raw claude runs unwrapped
ccpool enable         # removes the flag; rotation resumes
```

`CLAUDE_ROTATE_DISABLE=1` is a per-invocation transient kill-switch — equivalent to disabled but doesn't touch the on-disk flag.

### `ccpool version`

Print component versions: ccpool, caam, claude.

### `ccpool help` / `ccpool --help` / `ccpool -h`

Print the subcommand summary (the table at the top of `bin/ccpool`).

---

## Default mode

With no recognised subcommand, `ccpool` wraps `claude`:

```bash
ccpool                 # equivalent to: caam run claude --precheck --algorithm smart -- (no args)
ccpool -p "..."        # equivalent to: caam run claude --precheck --algorithm smart -- -p "..."
ccpool foo bar         # equivalent to: caam run claude --precheck --algorithm smart -- foo bar
```

Default mode skips rotation if:

- The kill-switch flag is set (`ccpool disable` or `CLAUDE_ROTATE_DISABLE=1`).
- `caam` is not on `$PATH`.
- Fewer than 2 profiles are configured (rotation has nothing to swap to).

In any of those cases, `ccpool` falls through to plain `claude "$@"`.

**Token injection:** Set `CCPOOL_USE_TOKEN=1` to have `ccpool` inject `CLAUDE_CODE_OAUTH_TOKEN` from the keychain before exec'ing caam. Most users don't need this — caam's own profile env handles auth.

---

## Configuration

Default location: `~/.config/ccpool/config.toml` (Linux) or `~/Library/Application Support/ccpool/config.toml` (macOS, preferred — XDG fallback also works).

Override paths (resolution order):

1. `$CCPOOL_CONFIG` env var
2. `~/.config/ccpool/config.toml` ($XDG_CONFIG_HOME)
3. `~/Library/Application Support/ccpool/config.toml` (macOS)
4. In-repo `ccpool.toml` (development mode)

### Schema

```toml
[meta]
schema_version = 1                   # bumped on incompatible changes
repo_owner     = ""                  # used in plist labels; empty → "local"

[provider]
name      = "claude"                 # claude (v1); codex/gemini stubs at v1, full at v1.1+
binary    = ""                       # auto-detected via $PATH if empty
caam_bin  = ""                       # auto-detected via $PATH if empty

# At least 2 profiles required for rotation. Names match ^[a-zA-Z0-9._-]+$
[[profile]]
name        = "personal"
email       = "you@example.com"
description = "primary account"
# config_dir_override = "/path/to/CLAUDE_CONFIG_DIR"   # advanced

[[profile]]
name        = "secondary"
email       = "you+work@example.com"
description = "second Claude Max"

[picker]
strategy_order     = ["usage_aware", "caam_smart", "round_robin"]
soft_threshold_pct = 85.0            # advisory notify
hard_threshold_pct = 95.0            # SATURATED — refuse spawn
usage_cache_ttl_s  = 5

[watcher]
enabled         = true
interval_s      = 300                # 5 min
network_every_n = 6                  # ~30 min between live usage fetches
min_gap_s       = 600                # anti-flap
dry_run         = false

[watchdog]
enabled               = true
five_hour_alert_pct   = 85.0
seven_day_alert_pct   = 90.0
extra_usage_alert_pct = 90.0
prune_keep_minutes    = 1440         # 24h caam backup retention

[storage]
backend                 = "auto"     # auto | keychain | secret_tool | env
env_file                = ""         # default: $XDG_DATA_HOME/ccpool/tokens.env
encrypt_env             = false      # opt-in encryption for env file
token_age_warn_days     = 330
token_age_critical_days = 360

[notify]
# Optional command. Receives JSON on stdin: {severity, code, message, profile, ts}
# command  = ["/usr/bin/notify-send", "{title}", "{message}"]
command    = []
severities = ["high", "critical"]

[shell]
manage_rc_file = true
files          = ["~/.zshrc", "~/.bashrc"]
alias_claude   = true                # alias claude=ccpool
export_flags   = true                # export CMAX_* env vars

[telemetry]
enabled        = false               # OFF by default
endpoint       = ""                  # POST'd anonymised JSON if set
include_errors = true
```

### Validation rules

`ccpool doctor` runs validation on load. See the finding codes table above. Hard errors prevent runtime; warnings surface but don't block.

| Rule | Severity |
|---|---|
| `meta.schema_version == 1` | hard error if drift |
| profile names unique | hard error |
| profile names match `^[a-zA-Z0-9._-]+$` | hard error |
| `picker.hard_threshold_pct > soft_threshold_pct` | hard error |
| `notify.command` is a list (security: no shell interpolation) | hard error |
| `[[profile]]` count ≥ 1 | warn at 0 |
| `[[profile]]` count ≥ 2 | warn at 1 |
| email matches loose RFC-5321 | warn |
| `notify.command[0]` resolvable | warn |
| `shell.files` ≥ 1 writable when `manage_rc_file` | warn |

---

## Filesystem layout

| Path | Purpose |
|---|---|
| `~/.config/ccpool/config.toml` | configuration |
| `$XDG_DATA_HOME/ccpool/tokens.env` | env-fallback token storage (mode 0600) |
| `$XDG_DATA_HOME/ccpool/tokens.json` | token age tracker (`{profile: {issued_at, account}}`) |
| `$XDG_DATA_HOME/ccpool/usage_cache.json` | last fetched usage snapshot |
| `$XDG_DATA_HOME/ccpool/watcher.ndjson` | rotation watcher event log |
| `$XDG_DATA_HOME/ccpool/disabled` | kill-switch sentinel |
| `$XDG_DATA_HOME/ccpool/degraded.flag` | endpoint-down sentinel |
| `$XDG_DATA_HOME/ccpool/saturated.flag` | all-profiles-over-hard sentinel |
| `~/Library/LaunchAgents/io.github.<owner>.ccpool.{watcher,watchdog}.plist` | macOS schedules |
| `~/.config/systemd/user/ccpool-{watcher,watchdog}.{service,timer}` | Linux schedules |
| `~/.local/share/caam/profiles/<provider>/<profile>/xdg_config/claude-code/.credentials.json` | per-profile claude session (caam-managed; we don't touch) |

---

## Environment variables

| Variable | Effect |
|---|---|
| `CCPOOL_CONFIG` | override config path |
| `CCPOOL_FORCE_ENV_STORAGE=1` | force env-file storage (bypass keychain entirely) |
| `CCPOOL_USE_TOKEN=1` | inject `CLAUDE_CODE_OAUTH_TOKEN` in default mode |
| `CLAUDE_ROTATE_DISABLE=1` | transient kill-switch (per-invocation) |
| `CLAUDE_ROTATE_COOLDOWN` | caam cooldown override (default `1h`) |
| `CLAUDE_ROTATE_MAX_RETRIES` | caam retry count (default `2`) |
| `CLAUDE_ROTATE_ALGO` | caam algorithm (default `smart`) |
| `CLAUDE_BIN` | override claude binary path |
| `CAAM_BIN` | override caam binary path |
| `CCPOOL_PY` | override Python interpreter (default `python3`) |
| `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME` | standard XDG overrides |

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | preflight or runtime error (descriptive stderr) |
| 2 | doctor: at least one CRITICAL finding |
| 64 | invalid usage (subcommand args wrong) |

`ccpool` itself never sets exit codes ≥ 100. If you see one, it came from the underlying `claude` or `caam` invocation.

---

## See also

- [INSTALL.md](INSTALL.md) — install paths
- [ARCHITECTURE.md](ARCHITECTURE.md) — module breakdown
- [THREAT_MODEL.md](THREAT_MODEL.md) — security boundary
- [PROVIDERS.md](PROVIDERS.md) — claude / codex / gemini
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — symptom-indexed fixes
- [COMPATIBILITY.md](COMPATIBILITY.md) — distro/version matrix
