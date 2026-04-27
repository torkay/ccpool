# ADR-0007 — Reliance on `/api/oauth/usage` (undocumented endpoint)

Date: 2026-04-27 · Status: accepted

## Context

Anthropic's `claude.ai` web UI shows live 5-hour and 7-day utilization plus PAYG ("extra usage") credit burn. The data comes from `GET https://api.anthropic.com/api/oauth/usage` with header `anthropic-beta: oauth-2025-04-20`. This endpoint is undocumented but stable enough to power the UI for many months, and is reverse-engineered by [`wcruz-br/claude-usage-dashboard`](https://github.com/wcruz-br/claude-usage-dashboard) and others.

cmaxctl's tier-1 picker uses this endpoint as ground truth: pick the lowest-utilization profile.

## Decision

**Use the endpoint as the primary picker signal**, with explicit fallback semantics for when it disappears.

## Risk acceptance

| Risk | Mitigation |
|---|---|
| Anthropic deprecates the endpoint (404/410) | tier-2 falls back to `caam robot next --strategy smart`; tier-3 to round-robin |
| Anthropic changes the response shape | parser tolerates missing fields; warn-not-fail; doctor surfaces shape drift |
| Anthropic adds auth requirements that block our token scope | already a partial issue: long-lived setup-tokens are `user:inference` scope and 403; we use per-profile access tokens (`user:profile` scope) for usage queries |
| Anthropic enforces a documented stable API at a different path | upgrade migration; major version bump |

## Hard saturation gate

When **all** profiles report ≥95% utilization, the picker returns `SATURATED_SENTINEL` and the caller refuses to spawn. Without this, fan-out spawns 429 immediately and waste tokens-on-error. The 95% threshold is below the OAuth refresh-race noise floor.

## Plan-B / Plan-C

| Tier | Source | Used when |
|---|---|---|
| 1 (primary) | `/api/oauth/usage` | endpoint reachable + token has `user:profile` scope |
| 2 (peer-promoted) | local JSONL block parser (`cmaxctl/blocks.py`) | endpoint unreachable; we still have local 5h-block heuristics |
| 3 (last-resort) | round-robin via on-disk counter | both above failed |

If 3 consecutive watcher ticks see 4xx from the endpoint, we activate Plan-B by flipping `cfg.picker.strategy_order` to skip `usage_aware`. Operator can revert with `cmax recover` once the endpoint comes back.

## What we will NOT do

- Browser-scrape (PinchTab, Playwright) at v1. Documented as Plan-C fallback only, triggered manually if Plan-B is also broken.
- Login session simulation. Out of scope; ToS-grey.

## Consequences

- README explicitly states the endpoint is undocumented and our reliance is best-effort.
- Doctor finding `oauth_endpoint_410` is CRITICAL severity.
- Test fixture `tests/fixtures/usage_responses/410.json` exercises the deprecation path.
