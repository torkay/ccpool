# Security

## Disclosure

If you discover a security issue in `cmaxctl`, please **do not** open a public issue.

Email: **security@<TBD>** (placeholder until v1.0; until then, open a GitHub issue marked `[security]` and we'll move it private)

We will acknowledge receipt within 7 days. We follow a 90-day disclosure window unless coordinated otherwise.

## Threat scope

In scope (we mitigate):
- Token leakage via env-var inheritance
- Accidental commit of `tokens.env`
- Anthropic `/api/oauth/usage` deprecation breaking the picker
- Malicious `config.toml` notify-command shell-injection
- macOS Keychain ACL bug #20553 leaving tokens unreadable

Out of scope (documented, not mitigated):
- Compromised operator machine (root attacker reading `tokens.env`) — single-user laptop trust model, same as `~/.zshrc` / SSH keys
- Multi-user shared machine — not a supported environment
- Mid-turn rotation of an in-flight `claude` process — Anthropic doesn't expose graceful re-auth

Full threat model: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Supply chain

- PyPI publishes happen via OIDC trusted publisher; no API tokens stored in the repo.
- Wheels are signed via [sigstore](https://www.sigstore.dev/).
- Releases are signed git tags. Verify with `git verify-tag v1.X.Y`.
- `caam` is a runtime dependency — verify it from upstream ([Dicklesworthstone/coding_agent_account_manager](https://github.com/Dicklesworthstone/coding_agent_account_manager)).

## Acknowledgements

Security researchers who responsibly disclose will be credited here unless they request anonymity.
