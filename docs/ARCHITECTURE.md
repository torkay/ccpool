# Architecture

`cmaxctl` is a thin orchestration layer over [`caam`](https://github.com/Dicklesworthstone/coding_agent_account_manager) and [`claude`](https://docs.claude.com/en/docs/claude-code/setup). It does no inference, holds no daemon, and stores no plaintext token outside the OS keychain (or an opt-in `tokens.env` 0600 fallback).

The whole tool is ~3500 lines of stdlib-only Python plus a 600-line bash dispatcher.

## Module map

```
bin/cmax                      # bash dispatcher; thin shell over the python CLI
cmaxctl/
├── cli.py                    # entrypoint (cmaxctl.cli:main); subcommand router
├── config.py                 # TOML loader/writer + dataclass schema + validation
├── paths.py                  # XDG resolution; per-OS path divergence
├── caam.py                   # caam binary wrapper (profile_ensure, robot_status, ...)
├── secrets.py                # keychain (macOS) + secret-tool (Linux) + tokens.env
├── usage.py                  # /api/oauth/usage HTTP client (5s file cache)
├── blocks.py                 # JSONL block parser fallback (peer of usage.py)
├── pick.py                   # 3-tier picker: usage_aware → caam_smart → round_robin
├── watcher.py                # rotation watcher tick (launchd/systemd-driven)
├── watchdog.py               # daily watchdog tick (prune + thresholds)
├── doctor.py                 # findings + autofix
├── identity.py               # token fingerprint + account identity marker
├── status.py                 # gather + render status snapshot
├── statusline.py             # one-line JSON for prompt integrations
├── notify.py                 # notify-hook abstraction (severity-gated)
├── platform.py               # OS detection + schedule install (launchd/systemd/cron)
├── shell.py                  # zsh/bash/fish managed-block writer
├── migrate.py                # v0 (personal substrate) → v1 detector + applier
└── _version.py               # __version__
```

## Why no resident daemon

Captured in [ADR-0004](ADRs/0004-no-resident-daemon.md). Three reasons:

1. **State persistence is the hard part of any rotation tool, not "what time is it".** A scheduled job (launchd interval / systemd timer) gives us "tick every 5 min" for free. Building a daemon to do the same thing buys nothing and adds a process the operator has to monitor.
2. **Reboots and crashes free.** A scheduled job gets re-fired by the OS. A daemon needs supervisor wiring or it dies invisibly.
3. **No memory footprint between ticks.** cmaxctl's working set during a tick is < 30 MB. Between ticks it's zero.

## Why stdlib-only

[ADR-0003](ADRs/0003-stdlib-only-python.md). `requests` would be nicer than `urllib`, but every dep is a supply-chain risk and a `pip install` failure mode for users. `urllib.request` works. `tomllib` (3.11+) works. Hand-rolled TOML writing works. The whole package depends on **nothing outside the Python stdlib**.

## Why no SQLite / cache layer

State is small. Tokens live in keychain (or `tokens.env`). Last-fetched usage is a 5-second JSON file cache. Watcher events are NDJSON append-only. Aggregate state across all this is a few hundred KB at steady state. Adding SQLite would mean adding a dep, a migration story, and a corruption surface for zero observable improvement.

## Sequence: `cmax setup` (first-run, fresh machine)

```
operator                   bin/cmax              cmaxctl.cli           caam              claude
   │                          │                      │                   │                  │
   │── cmax setup ───────────►│                      │                   │                  │
   │                          │── migrate detect ───►│                   │                  │
   │                          │◄────── JSON ─────────│                   │                  │
   │                          │  (no v0 detected)    │                   │                  │
   │                          │                      │                   │                  │
   │                          │── inventory ────────►│                   │                  │
   │                          │◄──── JSON ───────────│                   │                  │
   │                          │  (no profiles yet)   │                   │                  │
   │                          │                      │                   │                  │
   │                          │  prompt: profile name│                   │                  │
   │── personal ─────────────►│                      │                   │                  │
   │  prompt: email           │                      │                   │                  │
   │── you@example.com ──────►│                      │                   │                  │
   │                          │── caam profile add ────────────────────►│                  │
   │                          │◄────── ok ──────────────────────────────│                  │
   │                          │── caam env ─────────────────────────────►│                  │
   │                          │◄── CLAUDE_CONFIG_DIR=… ──────────────────│                  │
   │                          │                      │                   │                  │
   │                          │── claude auth login ───────────────────────────────────────►│
   │                          │     (browser opens)  │                   │                  │
   │◄── browser auth ─────────────────────────────────────────────────────────────────────────│
   │                          │◄────── creds.json written ─────────────────────────────────│
   │                          │                      │                   │                  │
   │                          │── identity_marker ──►│                   │                  │
   │                          │◄── (used to detect same-account collision)│                 │
   │                          │                      │                   │                  │
   │                          │── claude setup-token ──────────────────────────────────────►│
   │                          │◄── sk-ant-oat01-… ───────────────────────────────────────────│
   │                          │── secrets.set_token ►│                   │                  │
   │                          │   (keychain or env)  │                   │                  │
   │                          │                      │                   │                  │
   │                          │  (repeat per profile)│                   │                  │
   │                          │                      │                   │                  │
   │                          │── platform.schedule_install ►│           │                  │
   │                          │   (launchd / systemd / cron) │           │                  │
   │                          │                      │                   │                  │
   │                          │── shell.install ────►│                   │                  │
   │                          │   (rc managed block) │                   │                  │
   │                          │                      │                   │                  │
   │                          │── usage ────────────►│── /api/oauth/usage ──────►Anthropic  │
   │                          │◄── numbers ──────────│◄────── JSON ──────────────────────────│
   │◄── "All set." ───────────│                      │                   │                  │
```

## Sequence: `cmax pick` (subagent spawn)

```
caller (e.g. fleet)        cmax pick               cmaxctl.pick           usage cache
       │                        │                        │                     │
       │── eval "$(cmax pick)" ►│                        │                     │
       │                        │── load config ────────►│                     │
       │                        │◄── 2 profiles ─────────│                     │
       │                        │                        │                     │
       │                        │── tier 1: usage_aware ►│── read 5s cache ───►│
       │                        │                        │◄── snapshot ────────│
       │                        │                        │                     │
       │                        │  (lowest util wins)    │                     │
       │                        │  (or hard-saturated → SATURATED_SENTINEL)    │
       │                        │                        │                     │
       │                        │── caam env <picked> ───────────────►caam     │
       │                        │◄── CLAUDE_CONFIG_DIR + token ────────────────│
       │                        │                        │                     │
       │◄── KEY=VALUE lines ────│                        │                     │
       │  (ready for `eval`)    │                        │                     │
```

If usage tier fails (`/api/oauth/usage` returns 410 or times out), `pick` falls through to:

- **Tier 2:** `caam_blocks` peer — parses local `~/.claude/projects/**/*.jsonl` for active blocks.
- **Tier 3:** round-robin over healthy profiles.

When all profiles are above `picker.hard_threshold_pct`, `pick` emits `SATURATED_SENTINEL` and the caller is expected to refuse the spawn (`agent fleet spawn` enforces this).

## Why `pick` is the integration contract

[ADR / plan §3 #9](ADRs/) — `cmax pick` is pure env-emission. Any spawner (whether it's `agent fleet`, a custom orchestrator, or just a shell loop) inherits the right env via `eval "$(cmax pick)"`. cmaxctl doesn't link against the spawner; the spawner doesn't link against cmaxctl. The integration is a process boundary, which is the cheapest possible coupling.

## Provider abstraction

caam already supports multiple providers (claude, codex, gemini). At v1, cmaxctl ships **claude full + codex/gemini stubs** that raise `NotImplementedError("provider not implemented in cmaxctl 1.0")`. Each per-provider concern (login flow, token issuance, usage endpoint, identity marker) is a strategy table keyed by `cfg.provider.name`. Future PRs add codex and gemini full parity without touching the orchestration layer.

See [PROVIDERS.md](PROVIDERS.md) for the per-provider plan.

## Per-OS divergence

Almost every OS-conditional path lives in `platform.py` or `paths.py`:

| Concern | macOS | Linux |
|---|---|---|
| Schedule | `launchctl bootstrap`/`bootout` + plist | `systemctl --user enable` + `.service`/`.timer` (cron fallback) |
| Keychain | `security` CLI | `secret-tool` CLI (libsecret) |
| Browser open | `open <url>` | `xdg-open <url>` |
| Config dir | `~/Library/Application Support/cmaxctl` (preferred) | `$XDG_CONFIG_HOME/cmaxctl` |

The rest of the codebase is OS-agnostic. Adding Windows would mean adding a `WindowsScheduler` (Task Scheduler), a `WindowsCredentialManager` keychain backend, and a registry-aware paths module. PR-welcome but not v1.

## Threat model

Reproduced in [THREAT_MODEL.md](THREAT_MODEL.md). Highlights:

- **Tokens never live in env vars at rest** — only in keychain or `tokens.env` 0600.
- **`notify.command` must be a list** (no shell interpolation; can't `notify.command = "rm -rf /; …"`).
- **`tokens.env` is plaintext on disk** — same trust model as `~/.zshrc` / SSH keys; documented explicitly.
- **No mid-turn rotation** of an in-flight `claude` process — Anthropic doesn't expose graceful re-auth ([ADR-0010](ADRs/0010-no-mid-turn-rotation.md)).

## Telemetry

Off by default. When opted in, anonymised crash signature + version triplet only. Profile names, account emails, and any path containing `$HOME` are scrubbed before send. Full surface in [REFERENCE.md § telemetry](REFERENCE.md).

## Failure modes that have ADRs

- [ADR-0007](ADRs/0007-oauth-usage-undocumented-endpoint.md): `/api/oauth/usage` is undocumented. We expect it to break and have Plan-B (`caam_blocks` peer) wired in.
- [ADR-0005](ADRs/0005-keychain-then-env-fallback.md): Keychain ACL bug #20553 is a real production hazard. `secrets.py` always tries env-fallback if keychain refuses.
- [ADR-0010](ADRs/0010-no-mid-turn-rotation.md): mid-turn rotation is impossible at the OAuth layer; we don't try.

## See also

- [REFERENCE.md](REFERENCE.md) — full subcommand + config reference
- [THREAT_MODEL.md](THREAT_MODEL.md) — security boundary
- [PROVIDERS.md](PROVIDERS.md) — claude / codex / gemini plan
- [ADRs/](ADRs/) — every architectural decision with context
