# Troubleshooting

Indexed by **symptom**. Most fixes are one command. When in doubt, run `ccpool doctor --json` first — it surfaces the same finding codes referenced below.

---

## Install

### `caam: command not found` after `go install`

Symptoms: `ccpool doctor` reports `caam_missing` (CRITICAL).

**Fix:** add `~/go/bin` to `$PATH`:

```bash
echo 'export PATH="$HOME/go/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
caam --version    # should now resolve
```

If still missing, verify the install:

```bash
ls -la ~/go/bin/caam
go env GOPATH       # should match the dir caam was installed into
```

### `claude: command not found` after Anthropic install

Symptoms: `ccpool doctor` reports `claude_missing` (CRITICAL).

**Fix:** follow the [Anthropic install guide](https://docs.claude.com/en/docs/claude-code/setup). On Apple Silicon, `claude` typically lands in `/opt/homebrew/bin`; on Intel macOS in `/usr/local/bin`; on Linux in `~/.local/bin`. Verify with `which claude`.

If you've installed via npm and `claude` isn't on PATH, run:

```bash
npm config get prefix    # add the resulting bin/ to PATH
```

### `pipx install ccpool` fails: `ImportError: cannot import name 'tomllib'`

Symptoms: `pip` succeeds but `ccpool version` errors immediately.

**Cause:** Python < 3.11. `tomllib` was added in 3.11.

**Fix:**

```bash
brew install python@3.12        # macOS
apt install python3.12          # Ubuntu 24+
pipx install --python python3.12 ccpool
```

### `brew install ccpool` says formula not found

**Fix:** tap before install:

```bash
brew tap torkay/ccpool
brew install ccpool
```

### Linux: `secret-tool: command not found`

**Cause:** `libsecret-tools` not installed.

**Fix:**

```bash
# Debian/Ubuntu
sudo apt install libsecret-tools

# Fedora
sudo dnf install libsecret

# Arch
sudo pacman -S libsecret
```

If you're on a headless host without D-Bus, ccpool falls back to `tokens.env` 0600 and `ccpool doctor` will surface a LOW severity warning. That's fine — tokens still work, just plaintext on disk.

---

## Setup

### `ccpool setup` opens browser, login completes, but ccpool says credentials not present

Symptoms: `ccpool setup` fails on the same-account-guard step or token-issuance step. macOS specifically.

**Cause:** Apple Keychain ACL bug [#20553](https://github.com/anthropics/claude-code/issues/20553). Newly-namespaced credentials become unreadable after process exits.

**Fix:**

```bash
ccpool recover --rebuild-keychain     # wipes + re-adds keychain entries from tokens.env mirror
ccpool setup                          # retry
```

If that still fails, force env-only storage:

```bash
export CCPOOL_FORCE_ENV_STORAGE=1
ccpool setup
```

Add the export to `~/.zshrc` to persist.

### Same-account detected during setup

Symptoms: `SAME ACCOUNT DETECTED. <profile-a> signed into the same Claude account as: <profile-b>`.

**Cause:** Both profiles' Claude logins resolved to the same Claude Max account. Rotation has nothing to alternate to.

**Fix:** the offending profile is auto-purged. Re-run `ccpool setup` and ensure you sign into a different account when prompted. Tip: use a private/incognito browser window for the second login if your default browser is auto-filling the first account.

### `ccpool setup` hangs at "preparing isolated workspace"

**Cause:** caam profile-add shelling out and getting blocked.

**Fix:** check caam manually:

```bash
caam profile add claude debug-test --isolated     # interactive — type ctrl-c to bail
```

If caam itself hangs, file an issue upstream at <https://github.com/Dicklesworthstone/coding_agent_account_manager/issues>. ccpool can't help past this point.

---

## Runtime

### `ccpool usage` shows blank / "endpoint unreachable"

**Cause:** Anthropic's `/api/oauth/usage` endpoint failed. This is undocumented and explicitly fragile ([ADR-0007](ADRs/0007-oauth-usage-undocumented-endpoint.md)).

**Fix:** verify with raw network:

```bash
caam env claude personal | grep CLAUDE_CODE_OAUTH_TOKEN
# Try a curl with that token to see if it's a network issue or an Anthropic-side change
```

If the endpoint returns HTTP 410, ccpool auto-flips to `caam_blocks` peer (Plan-B). `ccpool doctor` will surface `oauth_endpoint_410` and re-prioritise the picker.

### `ccpool doctor` reports `oauth_endpoint_410`

CRITICAL. Auto-fix flips `cfg.picker.strategy_order` to skip `usage_aware`. The watcher and watchdog continue working off block-parser estimates.

```bash
ccpool doctor --fix
```

### Rotation isn't happening — `ccpool` keeps using the same account

**Diagnose:**

```bash
ccpool status              # are both profiles healthy?
ccpool doctor              # any HIGH/CRITICAL findings?
ccpool logs -n 50          # recent watcher events
```

Common causes:

| Cause | Fix |
|---|---|
| Watcher schedule didn't load | `ccpool doctor --fix` re-stages |
| Both accounts under soft threshold (no need to rotate yet) | working as designed; no fix |
| `ccpool disable` flag set | `ccpool enable` |
| `CLAUDE_ROTATE_DISABLE=1` in environment | `unset CLAUDE_ROTATE_DISABLE` |
| Only 1 profile configured | `ccpool setup` to add the second |

### Token age warning / critical

```bash
ccpool doctor              # shows token_age_warn or token_age_critical
ccpool rotate <profile>    # interactive; opens browser for setup-token
```

ccpool warns at 330 days (LOW) and goes critical at 360 days. Anthropic's long-lived tokens are nominally non-expiring but rotating annually is good hygiene.

### `ccpool disable` set but ccpool still trying to rotate

**Cause:** the on-disk flag wasn't written, or it's in the wrong directory.

**Fix:**

```bash
ls -la "${XDG_DATA_HOME:-$HOME/.local/share}/ccpool/disabled"
# If missing, force write:
touch "${XDG_DATA_HOME:-$HOME/.local/share}/ccpool/disabled"
```

---

## Schedules (launchd / systemd)

### macOS: launchd job not firing

**Diagnose:**

```bash
launchctl list | grep ccpool
launchctl print gui/$(id -u)/io.github.<owner>.ccpool.watcher
```

Look for a non-zero `last exit code`. If the plist isn't loaded:

```bash
ccpool doctor --fix        # re-stages plists
```

### Linux: systemd-user timer not firing

```bash
systemctl --user list-timers | grep ccpool
systemctl --user status ccpool-watcher.timer
journalctl --user -u ccpool-watcher.service -n 50
```

If `systemctl --user` itself fails (no D-Bus session), ccpool falls back to crontab automatically. Check:

```bash
crontab -l | grep ccpool
```

### Linux: cron fallback active but jobs not running

**Cause:** cron daemon not running on the host.

**Fix:**

```bash
sudo systemctl enable --now cron       # Debian/Ubuntu
sudo systemctl enable --now crond      # Fedora/Arch
```

If you can't run a system cron daemon (containers, restricted hosts), see [COMPATIBILITY.md § tier-3](COMPATIBILITY.md) for the no-scheduler degraded mode.

---

## Shell integration

### `ccpool` not found after install

**Cause:** install path not on `$PATH`.

**Fix:** find where the binary landed:

```bash
which ccpool || (
  pipx environment --value PIPX_BIN_DIR
  brew --prefix
  ls -la ~/.local/bin/ccpool
)
```

Add the directory to `$PATH` in your rc file.

### Managed-block in `~/.zshrc` got overwritten by another tool

**Cause:** oh-my-zsh, p10k, or a similar tool replaced the file outside our markers.

**Fix:**

```bash
ccpool doctor --fix        # detects zshrc_block_drift and re-writes the block
```

The managed block is wrapped in clear markers (`# >>> ccpool >>>` / `# <<< ccpool <<<`); ccpool never touches anything outside them.

### Fish shell: alias not picking up

**Cause:** fish reads `~/.config/fish/conf.d/*.fish` rather than a single rc file. ccpool writes to `~/.config/fish/conf.d/ccpool.fish`.

**Fix:**

```bash
ls -la ~/.config/fish/conf.d/ccpool.fish
# If missing:
ccpool doctor --fix
```

---

## Migration (v0 → v1)

### `ccpool migrate apply` aborts on "tokens.env conflicts"

**Cause:** v1 ccpool found an existing `tokens.env` it didn't write.

**Fix:** rename or remove the conflicting file:

```bash
mv ~/.local/share/ccpool/tokens.env ~/.local/share/ccpool/tokens.env.preserved
ccpool migrate apply
```

Then merge any tokens you actually need:

```bash
ccpool rotate    # re-issues fresh tokens for all profiles
```

### `ccpool migrate detect` says "detected: false" on a known-v0 machine

**Cause:** v0 lived in non-standard paths. Detection is signal-based — needs ≥2 of: caam profiles in the v0 personal layout, legacy `~/.zshrc` block, legacy launchd plist, legacy `~/.local/share/caam/tokens.json`.

**Fix:** migrate manually using the published schema, or file an issue with the unusual paths so we can add detection signals.

---

## Doctor finding code reference

For the full table, see [REFERENCE.md § doctor](REFERENCE.md#ccpool-doctor---fix---json). Quick lookup:

| Code | This file's section |
|---|---|
| `caam_missing` / `claude_missing` | [Install](#install) |
| `keychain_acl_corrupted` | [Setup](#setup) |
| `oauth_endpoint_410` | [Runtime](#runtime) |
| `plist_*` / `systemd_*` | [Schedules](#schedules-launchd--systemd) |
| `zshrc_block_drift` | [Shell integration](#shell-integration) |
| `token_age_*` | [Runtime](#runtime) |

---

## Last-resort reset

If ccpool is in a confused state and `ccpool doctor --fix` isn't enough:

```bash
ccpool disable
ccpool remove-shell
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/io.github.*.ccpool.*.plist  # macOS
systemctl --user disable ccpool-watcher.timer ccpool-watchdog.timer              # Linux
rm -rf ~/.config/ccpool ~/.local/share/ccpool ~/.cache/ccpool
# Tokens in keychain (macOS):
security delete-generic-password -s ccpool-token-personal 2>/dev/null
security delete-generic-password -s ccpool-token-secondary 2>/dev/null

# Now reinstall:
ccpool setup
```

This wipes all local ccpool state but leaves caam profiles + Claude credentials alone (so you don't have to re-OAuth).

## Filing a bug

If nothing here helps, file an issue at <https://github.com/torkay/ccpool/issues> with:

```bash
ccpool version
ccpool doctor --json
ccpool logs -n 100
uname -srm
python3 --version
caam --version
claude --version
```

Strip any token/email values before pasting.
