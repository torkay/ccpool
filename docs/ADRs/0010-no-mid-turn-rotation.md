# ADR-0010 — No mid-turn rotation of an in-flight `claude` process

Date: 2026-04-27 · Status: accepted

## Context

A natural feature request: "if account A starts a turn, and during that turn it crosses 95%, migrate the in-flight turn to account B so it completes." This is **not** what cmaxctl does, and not what it can do.

## Decision

cmaxctl rotates **at spawn boundaries only**. Once a `claude` process starts, the OAuth token used for that session is fixed for the lifetime of that process. If the active account caps mid-turn, that turn 429s.

## Why we can't do mid-turn rotation

- Claude Code holds OAuth state in-process (in-memory) via SDK abstractions.
- There is no graceful re-auth API exposed to external orchestrators.
- The OAuth refresh-race file lock (Anthropic [#43392](https://github.com/anthropics/claude-code/issues/43392), 7.5s budget) is for *automatic* refresh, not external swap.
- Forcing a swap by killing-and-respawning loses turn state — usually worse than letting it 429 and retry.

## What we DO instead

- **Pre-spawn rotation** ensures every new spawn lands on the lowest-utilization account.
- **Hard saturation gate** (95%) refuses to spawn when *all* accounts are nearly capped. Better to fail-fast than 429 mid-turn.
- **Watcher-tick rotation** (every 5 min) flips the active profile so spawns issued via wrappers/aliases that don't call our picker still benefit.
- **Token age tracker** rotates long-lived OAuth tokens proactively (~330 days).

## What this means for users

- Long-running turns (e.g. a 30-minute autonomous loop on a heavily-used account) can still cap mid-execution.
- Defensive pattern: chunk long workflows so spawn boundaries occur naturally; cmaxctl does the rest.
- Future: if Anthropic exposes a graceful re-auth API, this ADR may be revisited and superseded.

## Out of scope

- Process-level signal handling (SIGUSR1 etc) to trigger external swap — fragile, no upstream support.
- Hot-swap of `CLAUDE_CODE_OAUTH_TOKEN` env var — claude reads it at startup, ignores changes after.
