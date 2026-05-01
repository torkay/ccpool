# Compatibility

Where ccpool runs, what's verified in CI, and what's known to need attention.

## Tier-1 (CI-verified every PR)

| OS | Arch | Python | Secret backend | Scheduler | Shell rc |
|---|---|---|---|---|---|
| Ubuntu 24.04 | x86_64 | 3.11, 3.12 | secret-tool (libsecret) | systemd-user | bash, fish |
| Ubuntu 22.04 | x86_64 | 3.11, 3.12 | secret-tool (libsecret) | systemd-user | bash, fish |
| macOS 14 (Sonoma) | arm64 | 3.11, 3.12 | Keychain | launchd | zsh |

## Tier-2 (manually validated, not in CI)

| OS | Arch | Python | Secret backend | Scheduler | Notes |
|---|---|---|---|---|---|
| macOS 13 (Ventura) | arm64 | 3.11 | Keychain | launchd | Apple bug #20553 may surface — see TROUBLESHOOTING.md |
| Debian 12 (bookworm) | x86_64 | 3.11 | secret-tool | systemd-user | identical to Ubuntu 22 path |
| Fedora 40 | x86_64 | 3.12 | secret-tool | systemd-user | works; not in CI |
| Arch Linux | x86_64 | 3.12 | secret-tool | systemd-user | works; not in CI |

## Tier-3 (best-effort, fallback paths exist)

| OS | What works | Fallback chosen | Caveat |
|---|---|---|---|
| Headless Linux server (no D-Bus) | full CLI, env-only token store | `tokens.env` (mode 0600) | no native keyring; ADR-0008 |
| Linux without systemd-user | full CLI | crontab fallback | `ccpool doctor` reports cron mode; minute precision only |
| WSL2 (Ubuntu) | full CLI | secret-tool **if** `gnome-keyring` installed; else env-file | systemd-user works on WSL2 ≥ 0.67 |

## Explicitly unsupported

| OS | Why |
|---|---|
| Windows native | no plan; the personal substrate this was extracted from is unix-only |
| Android / iOS | n/a |

## Per-platform install commands

| OS | Recommended | One-liner |
|---|---|---|
| macOS | Homebrew | `brew tap torkay/ccpool && brew install ccpool && ccpool setup` |
| Ubuntu/Debian | pipx | `sudo apt install pipx libsecret-tools && pipx install ccpool && ccpool setup` |
| Fedora | pipx | `sudo dnf install pipx libsecret-tools && pipx install ccpool && ccpool setup` |
| Arch | pipx | `sudo pacman -S python-pipx libsecret && pipx install ccpool && ccpool setup` |
| Any unix | curl-bash | `curl -fsSL https://raw.githubusercontent.com/torkay/ccpool/main/install/install.sh \| bash` |

## What the CI lanes actually exercise

| Job | Scope | Skip-conditions |
|---|---|---|
| `unit` | All `tests/unit/` + `tests/integration/test_no_binary_degraded.py`; ruff lint | linux + py 3.11/3.12 across ubuntu 22/24 |
| `keyring` | `tests/integration/test_linux_keyring.py` under `dbus-run-session` + gnome-keyring | only ubuntu 24 + py 3.12; opt-in via `CCPOOL_TEST_LINUX_KEYRING=1` |
| `identity-scrub` | `grep` gate: zero personal identifiers anywhere outside fixtures + migrate.py | runs on every PR, hard-fails on hit |
| `package` | `python -m build` produces a sdist + wheel, uploads as artifact | every PR |

## Known caveats by platform

### macOS Keychain ACL bug (Apple #20553)
On certain macOS versions a Keychain entry created in one boot session loses readability after reboot, forcing a re-`ccpool setup`. ccpool detects this in `ccpool doctor` (finding code `keychain_acl_corrupted`) and offers `ccpool recover --rebuild-keychain` — see `docs/TROUBLESHOOTING.md`.

### Linux without `secret-tool`
If libsecret is absent, ccpool falls through to `tokens.env` at `$XDG_DATA_HOME/ccpool/tokens.env` with mode 0600. `ccpool doctor` reports `secrets_backend_inconsistent` (LOW) so the operator can choose to install libsecret-tools or accept the env-file backend.

### Linux without systemd-user
On hosts where `systemctl --user` isn't available (some VPS minimal images), ccpool uses `crontab` for the watcher + watchdog. Minute precision is the floor; the watcher runs every 5 minutes. Switch to systemd-user any time by re-running `ccpool setup`.

### `XDG_RUNTIME_DIR` not set
Headless boxes (CI runners, cron jobs) may not have `XDG_RUNTIME_DIR` exported. ccpool tolerates this and falls back to `XDG_DATA_HOME` for state files. Schedule install will detect and pick `cron` rather than `systemd-user`.

## Local Linux validation from macOS

Run the full Linux suite in a container without leaving your laptop:

```bash
./install/linux/run-tests-in-docker.sh           # ubuntu 24.04
./install/linux/run-tests-in-docker.sh 22.04     # pin a different version
CCPOOL_TEST_LINUX_KEYRING=1 ./install/linux/run-tests-in-docker.sh
```

This builds the same `Dockerfile.test` the CI uses and mounts the repo so wheels build in tree.
