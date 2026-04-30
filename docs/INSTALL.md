# Install

`cmaxctl` ships as a Python package (the import name) and a `cmax` shell binary (the user-facing command). Choose the install path that fits your setup. All paths are idempotent — re-running them is safe.

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| **Python ≥ 3.11** | runtime (stdlib only — see [ADR-0003](ADRs/0003-stdlib-only-python.md)) | `brew install python@3.12` (macOS) · `apt install python3.12` (Ubuntu) |
| **`caam`** | account isolation runtime dep ([ADR-0006](ADRs/0006-caam-as-runtime-dep.md)) | `go install github.com/Dicklesworthstone/coding_agent_account_manager/cmd/caam@latest` |
| **`claude`** | Anthropic Claude Code CLI | follow the [Anthropic install guide](https://docs.claude.com/en/docs/claude-code/setup) |
| **At least 2 Claude Max accounts** | rotation needs alternatives | sign up at [claude.ai](https://claude.ai/) |

`caam` and `claude` must resolve on `$PATH` after install. `cmax doctor` will tell you if either is missing.

## Install paths

### Homebrew (macOS recommended)

```bash
brew tap torkay/cmaxctl
brew install cmaxctl
cmax setup
```

Brew will pull `caam` as a `depends_on` dep. If you already installed `caam` via `go install`, brew will detect and skip.

### pipx (Linux + macOS)

```bash
pipx install cmaxctl
cmax setup
```

`pipx` keeps cmaxctl in its own venv so updates don't break system Python. Recommended for any non-brew install.

### curl-bash one-liner

```bash
curl -fsSL https://raw.githubusercontent.com/torkay/cmaxctl/main/install/install.sh | bash
```

The installer detects your OS, picks the best-available path (brew → pipx → pip --user), verifies `caam` and `claude` are present, and runs `cmax doctor` at the end. It exits non-zero if it can't find a clean path.

### pip (less preferred)

```bash
pip install --user cmaxctl
cmax setup
```

`pip --user` works but isolates poorly. If anything else on your machine bumps a transitive dep, cmaxctl could break — `pipx` is safer.

### From source (contributors)

```bash
git clone https://github.com/torkay/cmaxctl
cd cmaxctl
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cmax setup
```

Editable install + dev extras pull in `pytest` and `ruff`. See [CONTRIBUTING.md](../CONTRIBUTING.md).

### Linux packages (planned)

`.deb` and AUR (Arch) packages are queued for v1.1. Track progress at the upstream repo. Until then, `pipx install cmaxctl` is the canonical Linux path.

## Verify

After any install, run:

```bash
cmax version       # cmaxctl + caam + claude versions
cmax doctor        # health check; should be green or surface specific findings
cmax setup         # interactive bootstrap
```

`cmax doctor` exits 0 if findings are all `LOW` or `MEDIUM`. `HIGH`/`CRITICAL` findings exit non-zero with a diagnostic message and a remediation hint.

When setup completes, run:

```bash
cmax usage         # live per-account utilization
cmax statusline    # one-line JSON for prompt integrations
```

If `cmax usage` returns numbers, you're done.

## Per-OS specifics

### macOS

- **launchd** is used for the rotation watcher and daily watchdog (no resident daemon — see [ADR-0004](ADRs/0004-no-resident-daemon.md)).
- **Keychain** is the default secret backend (with `tokens.env` 0600 fallback if Keychain is locked or hits ACL bug [#20553](https://github.com/anthropics/claude-code/issues/20553)).
- **Apple Silicon + Intel** both supported; brew picks the right slot.
- **macOS 13+** required for `launchctl bootstrap`. macOS 12 falls back to legacy `launchctl load`.

### Linux

- **systemd-user** is preferred for schedules. Containers and minimal distros without systemd-user fall back to `crontab` automatically.
- **libsecret / gnome-keyring** is the keychain backend. `secret-tool` CLI must be installed: `apt install libsecret-tools`.
- **Headless / no D-Bus**: cmaxctl falls back to `tokens.env` 0600 storage. `cmax doctor` will surface `keychain_unavailable` (LOW severity).
- See [COMPATIBILITY.md](COMPATIBILITY.md) for the per-distro tier matrix.

### Windows

Not supported at v1. POSIX shell + keyring assumptions don't carry over. PR-welcome.

## Upgrade

| Install path | Upgrade |
|---|---|
| Homebrew | `brew upgrade cmaxctl` |
| pipx | `pipx upgrade cmaxctl` |
| pip | `pip install --user --upgrade cmaxctl` |
| Source | `git pull && pip install -e .` |

After upgrade, run `cmax doctor` to surface any config-schema migrations.

## Uninstall

```bash
cmax disable                                # stop rotation; raw `claude` keeps working
cmax remove-shell                           # strip managed-block from rc files (optional)
launchctl bootstout gui/$(id -u) ~/Library/LaunchAgents/io.github.*.cmaxctl.*.plist  # macOS
systemctl --user disable cmaxctl-watcher.timer cmaxctl-watchdog.timer                # Linux
brew uninstall cmaxctl                      # or: pipx uninstall cmaxctl
rm -rf ~/.config/cmaxctl ~/.local/share/cmaxctl ~/.cache/cmaxctl
# Tokens in keychain: `security delete-generic-password -s cmaxctl-token-<profile>`
```

`cmax recover` does step 3 (schedules) automatically and is the safer entry point.

## Troubleshooting install

| Symptom | Likely cause | Fix |
|---|---|---|
| `caam: command not found` after install | `~/go/bin` not on `$PATH` | add `export PATH="$HOME/go/bin:$PATH"` to your rc file |
| `cmax setup` opens browser, login completes, but cmaxctl says "credentials not present" | macOS Keychain ACL bug #20553 | `cmax recover --rebuild-keychain` |
| `pipx install cmaxctl` fails with `cannot find toml.lib` | Python < 3.11 | upgrade Python; cmaxctl uses `tomllib` (stdlib 3.11+) |
| Linux: `secret-tool: command not found` | `libsecret-tools` not installed | `apt install libsecret-tools` (Debian/Ubuntu) or distro-equivalent |
| Linux: `dbus-launch` missing | minimal containers without D-Bus | use `tokens.env` fallback; `cmax doctor` will warn but rotation still works |
| `brew install` fails with formula not found | tap not refreshed | `brew tap torkay/cmaxctl` first, then install |
| `cmax doctor` reports `oauth_endpoint_410` | Anthropic deprecated `/api/oauth/usage` | upgrade cmaxctl; falls back to `caam_blocks` peer ([ADR-0007](ADRs/0007-oauth-usage-undocumented-endpoint.md)) |

For deeper symptoms, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
