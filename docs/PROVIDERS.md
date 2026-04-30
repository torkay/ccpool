# Providers

cmaxctl is designed around `caam`'s multi-provider support, which already covers `claude`, `codex`, and `gemini`. At v1.0, cmaxctl ships **claude full support + codex/gemini stubs**.

## Status matrix

| Provider | OAuth login | Long-lived tokens | Usage endpoint | Block parser | Identity marker | Status |
|---|---|---|---|---|---|---|
| `claude` | ✓ | ✓ | ✓ `/api/oauth/usage` | ✓ JSONL | ✓ resets_at + monthly_limit | **full** |
| `codex` | – | – | – | – | – | stub (raises `NotImplementedError`) |
| `gemini` | – | – | – | – | – | stub (raises `NotImplementedError`) |

## Why claude only at v1

caam upstream supports all three providers, but cmaxctl needs to know per-provider:

- **OAuth login flow shape** — flag names, prompts, browser-vs-headless paths.
- **Long-lived token issuance** — the equivalent of `claude setup-token`.
- **Usage endpoint** — the equivalent of `/api/oauth/usage` (likely undocumented for all three).
- **Identity marker** — a stable account-fingerprint we can use to detect same-account collisions.
- **Block parser** — local JSONL or equivalent for offline usage estimation.

Of these, only the claude surface is documented enough today (and we treat it as fragile — see [ADR-0007](ADRs/0007-oauth-usage-undocumented-endpoint.md)). codex and gemini equivalents need first-hand investigation that can be done without rushing v1.

## What the stubs actually do

Setting `cfg.provider.name = "codex"` (or `"gemini"`) causes cmaxctl to:

1. **`cmax setup`**: refuses with a clear error pointing at the tracking issue.
2. **`cmax pick` / default mode**: passes through to `caam run codex --precheck …` so caam handles whatever it can natively. cmaxctl's usage-aware tier is skipped (no endpoint client).
3. **`cmax doctor`**: reports `provider_not_implemented` (HIGH) until a real implementation lands.

Setting `cfg.provider.name = "claude"` (default) is the only path that exercises every code path.

## What v1.1+ needs to ship a provider

For each of codex / gemini, the work is:

| Item | Effort | Notes |
|---|---|---|
| Login flow strategy | small | `cfg.provider` discriminates; shell dispatcher already pluggable |
| Long-lived token issuance | small | maps to a single CLI invocation per provider |
| Usage endpoint client | medium | likely undocumented per-provider; needs reverse-engineering or upstream chat |
| Block parser | medium | each provider's local-cache file format must be parsed; some don't have one |
| Identity marker | small | first-12-chars-hash of access token works as a fallback |
| Test fixtures | medium | mock binaries per `tests/fixtures/bin/{caam,claude}` style |
| ADR | small | document the provider-specific decisions |

A single contributor familiar with the target provider should be able to ship one in a long weekend.

## Adding a new provider

The skeleton:

1. **Add a strategy table entry.** `cmaxctl/providers/<name>.py` exports `LOGIN`, `TOKEN_ISSUE`, `USAGE_FETCH`, `IDENTITY_MARKER` callables that follow the same shape as the claude implementation.
2. **Wire the dispatch.** `cmaxctl/cli.py` and `bin/cmax` already discriminate on `cfg.provider.name`; just add a branch.
3. **Add a mock binary.** `tests/fixtures/bin/<provider>` with the same env-driven control surface as the claude mock.
4. **Add bats + pytest coverage.** Existing tests can be parametrised.
5. **Document.** Add a section to this file; add an ADR if the provider forces a non-obvious decision.

## Tracking issues

| Provider | Issue | Status |
|---|---|---|
| codex | TBD (file on first user request) | not yet filed |
| gemini | TBD | not yet filed |

When you file the tracking issue, link it from this file and from `cmaxctl/providers/<name>.py` so the stub error message can point users at it.

## See also

- [ARCHITECTURE.md § provider abstraction](ARCHITECTURE.md#provider-abstraction)
- [REFERENCE.md § configuration](REFERENCE.md#configuration) — `[provider]` block
- caam upstream: <https://github.com/Dicklesworthstone/coding_agent_account_manager>
