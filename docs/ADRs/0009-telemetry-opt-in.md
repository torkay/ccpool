# ADR-0009 — Telemetry: opt-in, off by default

Date: 2026-04-27 · Status: accepted

## Context

Telemetry helps maintainers understand which features are used, which OS+Python combos are common, and where crashes happen. It can also be a privacy footgun (sending hostname / paths / personal identifiers without explicit consent).

## Decision

**Telemetry is OFF by default.** No data leaves the operator's machine without explicit opt-in via `cfg.telemetry.enabled = true`.

When enabled, the payload is minimised and anonymised:

| Allowed | Prohibited |
|---|---|
| OS + version (`darwin 25.2.0`) | hostname, username |
| Python version | working directory |
| cmaxctl + caam + claude versions | tokens (any kind) |
| anonymised crash signature (`file:line + ExceptionClass`) | full traceback content (may contain user paths) |
| feature counter (`rotate_fired`) | profile names, account emails |
| install path used (brew/curl/pipx/pip) | path with `$HOME` |

## Endpoint

Operator-supplied via `cfg.telemetry.endpoint`. We may stand up a public collector at `metrics.cmaxctl.dev` post-v1.0 — but only if it remains true-opt-in (no default value pointing at it).

## Why opt-in

- Open-source PII collection without explicit consent is a violation of trust.
- We do not have a hosted collector at v1.0; default-on telemetry would 404 silently or get sent to a placeholder.
- Power users (security-conscious, air-gapped) get a working install with zero outbound non-Anthropic traffic.

## Consequences

- We have less data on real-world usage than competitors with default-on telemetry.
- README + CHANGELOG don't include "telemetry default-on" surprise upgrades.
- Adding a default-on endpoint in the future requires a new ADR overriding this one + a MAJOR version bump (since it changes user privacy posture).

## What we DO collect (without opt-in)

Local-only:
- `watcher.ndjson` (rotation events) — never leaves the machine
- `usage_cache.json` (5-second utilization snapshots) — never leaves the machine

These exist for diagnostics (`cmax logs`) and the picker, respectively. They contain no operator identifiers.
