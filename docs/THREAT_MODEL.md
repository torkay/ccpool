# Threat model

Reproduced from the canonical hardening plan §15. Updated as new threats land or mitigations change.

## Assets

| Asset | Sensitivity | Storage |
|---|---|---|
| Claude long-lived OAuth token (`sk-ant-oat01-...`) | high — per-account inference cap | macOS keychain or `tokens.env` 0600 |
| Per-profile access token in `.credentials.json` | high — short-lived, valid | provider's own files (we don't move them) |
| Claude account email | medium — PII | `config.toml` |
| Usage telemetry (5h util, 7d util, PAYG) | medium — usage patterns | `usage_cache.json` |
| Watcher event log | low | `watcher.ndjson` (no token data) |

## Threats

| # | Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| T1 | Token leaked via env var inheritance | medium | high | clear `CLAUDE_CODE_OAUTH_TOKEN` in subprocess wrappers when not needed; document env-isolation pattern |
| T2 | `tokens.env` committed to repo accidentally | medium | high | `.gitignore` ships ignoring `tokens.env` + `usage_cache.json` + `*.flag`; doctor warns when state-dir inside a git repo |
| T3 | Keychain ACL bug #20553 makes token unreadable post-reboot | medium | medium | `secrets.py` falls back to `tokens.env`; doctor surfaces `keychain_acl_corrupted` |
| T4 | Anthropic deprecates `/api/oauth/usage` | medium | medium | picker tier-2 fallback to caam smart; tier-3 to round-robin; doctor surfaces 410 → activates Plan-B |
| T5 | Malicious `config.toml` (notify command runs arbitrary shell) | low | high | `notify.command` must be a list (no shell interpolation); validated at load |
| T6 | Compromised PyPI package (typosquat) | low | high | publish only via OIDC + signed wheels (sigstore); README + INSTALL.md show exact package + repo URL |
| T7 | caam binary trojaned | low | very high | document upstream verification; pin caam version in CI; suggest hash-pinning |
| T8 | `notify.command` exfiltrates state | low | high | command receives only the alert JSON, not tokens; document this contract |
| T9 | Lost state-dir → operator can't tell if tokens still in keychain | low | low | `ccpool doctor` enumerates keychain entries via known service IDs |
| T10 | `claude setup-token` issuing long-lived inference tokens that never expire | n/a (Anthropic-side) | medium | token age tracker warns at 330d, critical at 360d; `ccpool rotate` rotates |

### T5 in detail (config-driven shell injection)

The `notify.command` config key is the largest attack surface for a malicious `config.toml`. We mitigate by:

1. **Type enforcement at load time.** `config.py:_coerce` rejects any non-list value. A user who edits `config.toml` to set `notify.command = "rm -rf ~"` ends up with `notify.command = []` after load.
2. **No shell interpolation.** When `notify.fire()` invokes the command, it uses `subprocess.run(cmd, shell=False, ...)`. Even if a list element contains shell metacharacters, they're passed as a literal arg, not a shell expression.
3. **Token isolation.** The command receives a JSON payload on stdin: `{severity, code, message, profile, ts}`. Tokens are never in this payload.

Documented in [REFERENCE.md § notify](REFERENCE.md#notify).

### T6 in detail (PyPI typosquat)

Two layers of mitigation:

1. **Trusted publishing via OIDC.** The `release.yml` workflow publishes to PyPI using GitHub's OIDC identity provider; no API token lives in the repo or in CI secrets.
2. **Sigstore signing** is queued for v1.1 — wheels will be signed with the GitHub Actions identity, verifiable via `pypi-attestations`.

The package name itself is somewhat protected: `ccpool` is a clean grab on PyPI (the `ccpool` name is already taken by an unrelated MIT-6.01 circuit sim, and we explicitly avoided it — see [ADR-0001](ADRs/0001-package-name.md)).

## Out of threat scope

| Excluded threat | Reason |
|---|---|
| Compromised operator machine (root attacker reads `tokens.env`) | plaintext storage on single-user laptop is acceptable per same model as `~/.zshrc`/SSH keys; SECURITY.md states explicitly |
| Multi-user shared machine | not supported; documented |
| Mid-turn rotation of in-flight `claude` process | Anthropic doesn't expose graceful re-auth |

These are deliberate scope choices, not oversights. ccpool assumes:

- The OS user owns the machine (single-user model).
- The OS keychain is trustworthy (or `tokens.env` 0600 is acceptable to the operator).
- The Anthropic OAuth flow itself is sound — we don't try to harden it.

If your threat model includes any of these, ccpool is the wrong tool.

## Reporting a vulnerability

See [SECURITY.md](../SECURITY.md). 90-day disclosure window. Use `security@<TBD>` (set on first publish).

## See also

- [SECURITY.md](../SECURITY.md) — disclosure process
- [ADR-0008](ADRs/0008-token-storage-encryption-stance.md) — encryption opt-in stance
- [ADR-0009](ADRs/0009-telemetry-opt-in.md) — telemetry posture
