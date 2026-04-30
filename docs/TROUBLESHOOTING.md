# Troubleshooting

Indexed by **symptom**. Most fixes are one command. When in doubt, run `cmax doctor --json` first — it surfaces the same finding codes referenced below.

---

## Install

### `caam: command not found` after `go install`

Symptoms: `cmax doctor` reports `caam_missing` (CRITICAL).

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

Symptoms: `cmax doctor` reports `claude_missing` (CRITICAL).

**Fix:** follow the [Anthropic install guide](https://docs.claude.com/en/docs/claude-code/setup). On Apple Silicon, `claude` typically lands in `/opt/homebrew/bin`; on Intel macOS in `/usr/local/bin`; on Linux in `~/.local/bin`. Verify with `which claude`.

If you've installed via npm and `claude` isn't on PATH, run:

```bash
npm config get prefix    # add the resulting bin/ to PATH
```

### `pipx install cmaxctl` fails: `ImportError: cannot import name 'tomllib'`

Symptoms: `pip` succeeds but `cmax version` errors immediately.

**Cause:** Python < 3.11. `tomllib` was added in 3.11.

**Fix:**

```bash
brew install python@3.12        # macOS
apt install python3.12          # Ubuntu 24+
pipx install --python python3.12 cmaxctl
```

### `brew install cmaxctl` says formula not found

**Fix:** tap before install:

```bash
brew tap torkay/cmaxctl
brew install cmaxctl
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

If you're on a headless host without D-Bus, cmaxctl falls back to `tokens.env` 0600 and `cmax doctor` will surface a LOW severity warning. That's fine — tokens still work, just plaintext on disk.

---

## Setup

### `cmax setup` opens browser, login completes, but cmaxctl says credentials not present

Symptoms: `cmax setup` fails on the same-account-guard step or token-issuance step. macOS specifically.

**Cause:** Apple Keychain ACL bug [#20553](https://github.com/anthropics/claude-code/issues/20553). Newly-namespaced credentials become unreadable after process exits.

**Fix:**

```bash
cmax recover --rebuild-keychain     # wipes + re-adds keychain entries from tokens.env mirror
cmax setup                          # retry
```

If that still fails, force env-only storage:

```bash
export CMAXCTL_FORCE_ENV_STORAGE=1
cmax setup
```

Add the export to `~/.zshrc` to persist.

### Same-account detected during setup

Symptoms: `SAME ACCOUNT DETECTED. <profile-a> signed into the same Claude account as: <profile-b>`.

**Cause:** Both profiles' Claude logins resolved to the same Claude Max account. Rotation has nothing to alternate to.

**Fix:** the offending profile is auto-purged. Re-run `cmax setup` and ensure you sign into a different account when prompted. Tip: use a private/incognito browser window for the second login if your default browser is auto-filling the first account.

### `cmax setup` hangs at "preparing isolated workspace"

**Cause:** caam profile-add shelling out and getting blocked.

**Fix:** check caam manually:

```bash
caam profile add claude debug-test --isolated     # interactive — type ctrl-c to bail
```

If caam itself hangs, file an issue upstream at <https://github.com/Dicklesworthstone/coding_agent_account_manager/issues>. cmaxctl can't help past this point.

---

## Runtime

### `cmax usage` shows blank / "endpoint unreachable"

**Cause:** Anthropic's `/api/oauth/usage` endpoint failed. This is undocumented and explicitly fragile ([ADR-0007](ADRs/0007-oauth-usage-undocumented-endpoint.md)).

**Fix:** verify with raw network:

```bash
caam env claude personal | grep CLAUDE_CODE_OAUTH_TOKEN
# Try a curl with that token to see if it's a network issue or an Anthropic-side change
```

If the endpoint returns HTTP 410, cmaxctl auto-flips to `caam_blocks` peer (Plan-B). `cmax doctor` will surface `oauth_endpoint_410` and re-prioritise the picker.

### `cmax doctor` reports `oauth_endpoint_410`

CRITICAL. Auto-fix flips `cfg.picker.strategy_order` to skip `usage_aware`. The watcher and watchdog continue working off block-parser estimates.

```bash
cmax doctor --fix
```

### Rotation isn't happening — `cmax` keeps using the same account

**Diagnose:**

```bash
cmax status              # are both profiles healthy?
cmax doctor              # any HIGH/CRITICAL findings?
cmax logs -n 50          # recent watcher events
```

Common causes:

| Cause | Fix |
|---|---|
| Watcher schedule didn't load | `cmax doctor --fix` re-stages |
| Both accounts under soft threshold (no need to rotate yet) | working as designed; no fix |
| `cmax disable` flag set | `cmax enable` |
| `CLAUDE_ROTATE_DISABLE=1` in environment | `unset CLAUDE_ROTATE_DISABLE` |
| Only 1 profile configured | `cmax setup` to add the second |

### Token age warning / critical

```bash
cmax doctor              # shows token_age_warn or token_age_critical
cmax rotate <profile>    # interactive; opens browser for setup-token
```

cmaxctl warns at 330 days (LOW) and goes critical at 360 days. Anthropic's long-lived tokens are nominally non-expiring but rotating annually is good hygiene.

### `cmax disable` set but cmaxctl still trying to rotate

**Cause:** the on-disk flag wasn't written, or it's in the wrong directory.

**Fix:**

```bash
ls -la "${XDG_DATA_HOME:-$HOME/.local/share}/cmaxctl/disabled"
# If missing, force write:
touch "${XDG_DATA_HOME:-$HOME/.local/share}/cmaxctl/disabled"
```

---

## Schedules (launchd / systemd)

### macOS: launchd job not firing

**Diagnose:**

```bash
launchctl list | grep cmaxctl
launchctl print gui/$(id -u)/io.github.<owner>.cmaxctl.watcher
```

Look for a non-zero `last exit code`. If the plist isn't loaded:

```bash
cmax doctor --fix        # re-stages plists
```

### Linux: systemd-user timer not firing

```bash
systemctl --user list-timers | grep cmaxctl
systemctl --user status cmaxctl-watcher.timer
journalctl --user -u cmaxctl-watcher.service -n 50
```

If `systemctl --user` itself fails (no D-Bus session), cmaxctl falls back to crontab automatically. Check:

```bash
crontab -l | grep cmaxctl
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

### `cmax` not found after install

**Cause:** install path not on `$PATH`.

**Fix:** find where the binary landed:

```bash
which cmax || (
  pipx environment --value PIPX_BIN_DIR
  brew --prefix
  ls -la ~/.local/bin/cmax
)
```

Add the directory to `$PATH` in your rc file.

### Managed-block in `~/.zshrc` got overwritten by another tool

**Cause:** oh-my-zsh, p10k, or a similar tool replaced the file outside our markers.

**Fix:**

```bash
cmax doctor --fix        # detects zshrc_block_drift and re-writes the block
```

The managed block is wrapped in clear markers (`# >>> cmaxctl >>>` / `# <<< cmaxctl <<<`); cmaxctl never touches anything outside them.

### Fish shell: alias not picking up

**Cause:** fish reads `~/.config/fish/conf.d/*.fish` rather than a single rc file. cmaxctl writes to `~/.config/fish/conf.d/cmaxctl.fish`.

**Fix:**

```bash
ls -la ~/.config/fish/conf.d/cmaxctl.fish
# If missing:
cmax doctor --fix
```

---

## Migration (v0 → v1)

### `cmax migrate apply` aborts on "tokens.env conflicts"

**Cause:** v1 cmaxctl found an existing `tokens.env` it didn't write.

**Fix:** rename or remove the conflicting file:

```bash
mv ~/.local/share/cmaxctl/tokens.env ~/.local/share/cmaxctl/tokens.env.preserved
cmax migrate apply
```

Then merge any tokens you actually need:

```bash
cmax rotate    # re-issues fresh tokens for all profiles
```

### `cmax migrate detect` says "detected: false" on a known-v0 machine

**Cause:** v0 lived in non-standard paths. Detection is signal-based — needs ≥2 of: caam profiles in the v0 personal layout, legacy `~/.zshrc` block, legacy launchd plist, legacy `~/.local/share/caam/tokens.json`.

**Fix:** migrate manually using the published schema, or file an issue with the unusual paths so we can add detection signals.

---

## Doctor finding code reference

For the full table, see [REFERENCE.md § doctor](REFERENCE.md#cmax-doctor---fix---json). Quick lookup:

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

If cmaxctl is in a confused state and `cmax doctor --fix` isn't enough:

```bash
cmax disable
cmax remove-shell
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/io.github.*.cmaxctl.*.plist  # macOS
systemctl --user disable cmaxctl-watcher.timer cmaxctl-watchdog.timer              # Linux
rm -rf ~/.config/cmaxctl ~/.local/share/cmaxctl ~/.cache/cmaxctl
# Tokens in keychain (macOS):
security delete-generic-password -s cmaxctl-token-personal 2>/dev/null
security delete-generic-password -s cmaxctl-token-secondary 2>/dev/null

# Now reinstall:
cmax setup
```

This wipes all local cmaxctl state but leaves caam profiles + Claude credentials alone (so you don't have to re-OAuth).

## Filing a bug

If nothing here helps, file an issue at <https://github.com/torkay/cmaxctl/issues> with:

```bash
cmax version
cmax doctor --json
cmax logs -n 100
uname -srm
python3 --version
caam --version
claude --version
```

Strip any token/email values before pasting.
