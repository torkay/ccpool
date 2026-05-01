# ADR-0008 — Token storage encryption stance

Date: 2026-04-27 · Status: accepted

## Context

Long-lived OAuth tokens have ~1-year validity (Anthropic side; our age tracker warns at 330d, critical at 360d). They grant the bearer Claude inference access against the operator's account. Storage options range from "plaintext file" to "OS-managed encrypted vault".

## Decision

**Default: OS keychain (encrypted at rest by the OS) + plaintext `tokens.env` fallback (mode 0600).** No application-layer encryption.

## Why no application encryption

| Option | Pro | Con |
|---|---|---|
| App-layer encryption with operator-supplied passphrase | encrypted at rest even without keychain | UX prompt on every read; hard to script; lockout-on-forgotten-passphrase |
| App-layer encryption with hardcoded key from `~/.config/ccpool/secret.key` | no UX prompt | the key file is plaintext; breaks the threat model premise |
| Use OS keychain or fall through to plaintext | matches threat model; simple | plaintext file IS plaintext |

The plaintext file lives in `$XDG_DATA_HOME/ccpool/tokens.env` mode 0600 — only the owning user can read it. This is the same trust model as:
- `~/.zshrc` / `~/.bashrc` (often contain API keys via `export FOO=...`)
- `~/.aws/credentials`, `~/.config/gh/hosts.yml`
- `~/.ssh/id_*` private keys (passphrase-optional)

The threat model (`docs/THREAT_MODEL.md`) explicitly excludes "compromised operator machine" — a root attacker reading these files is OOS for ccpool.

## When this changes

- Operator-supplied encryption: if a community demand surfaces for this, we add `[storage.encrypt]` config support behind opt-in flag, with the documented UX cost.
- Hardware-backed (TPM, Touch ID): macOS keychain already does this; on Linux, libsecret + GNOME-Keyring do too. We don't reimplement.

## Consequences

- Encrypted-volume operators (FileVault, LUKS) get encryption for free at the FS layer.
- Operators on shared machines should not use ccpool (documented as OOS in SECURITY.md).
- `ccpool doctor` warns when state-dir is inside a git repository (T2 risk: accidental commit).
