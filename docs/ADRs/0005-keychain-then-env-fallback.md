# ADR-0005 — Token storage: keychain preferred, .env fallback

Date: 2026-04-27 · Status: accepted

## Context

Long-lived OAuth tokens (`sk-ant-oat01-…`) need somewhere to live across reboots. Options:

| Option | Pro | Con |
|---|---|---|
| macOS Keychain / libsecret | OS-managed; encrypted at rest | locked-out post-reboot bug #20553 (Apple); no Linux-secret-tool everywhere |
| 1Password CLI | cross-machine sync | desktop app integration broken on operator's machine (verified); BYO dep |
| `.env` file 0600 | always works | plaintext on disk |
| Encrypted `.env` (operator-supplied passphrase) | encrypted | UX cost: prompt on every read |

## Decision

**Keychain preferred, `.env` fallback, transparent.**

- Write attempts keychain first.
- On keychain failure (any cause), fall through to `~/.local/share/ccpool/tokens.env` mode 0600.
- Read attempts `.env` first (so a deliberate fallback wins over a stale keychain entry), then keychain.
- Operator can force `.env`-only via `CAAM_FORCE_ENV_STORAGE=1` (legacy var name preserved for now; alias `CCPOOL_FORCE_ENV_STORAGE=1` added).

## Why this ordering

- Most users get keychain. Best-case secure-by-default.
- Apple keychain ACL bug #20553 strikes some machines. Without a fallback we'd be hard-broken on those. Fallback means worst-case = working.
- Some Linux distros lack libsecret / gnome-keyring (containers, Alpine). Same fallback applies.
- The `.env` file lives in a directory only the operator can read; same trust model as `~/.zshrc` / `~/.ssh/`.

## What we are NOT doing

- We do NOT encrypt the `.env` file by default. Reasoning:
  - The threat model says "compromised operator machine = out of scope" (single-user laptop).
  - Encryption adds prompt UX cost for every read.
  - If a security-conscious operator wants encryption, `.env` can sit on an encrypted volume (FileVault / LUKS) — same as their `~/.ssh/`.
- We do NOT integrate 1Password CLI. Verified-broken on operator's reference machine; if community demand surfaces, separate ADR.

## Consequences

- `ccpool doctor` exposes both backends and surfaces drift between them.
- `ccpool rotate` writes to whichever backend the previous token used (defaulting keychain).
- The keychain service prefix is `ccpool-token-` (was `caam-claude-token-` in v0); `migrate.py` rewrites old entries.
