# ADR-0002 — License: MIT

Date: 2026-04-27 · Status: accepted

## Context

A public OSS project needs a license. We considered MIT, Apache 2.0, and BSD-3.

## Decision

**MIT.**

## Alternatives considered

| License | Pro | Con | Verdict |
|---|---|---|---|
| MIT | maximum adoption; minimal friction; well-understood | no patent grant | chosen |
| Apache 2.0 | explicit patent grant; widely respected in enterprise | longer; minor friction in some contexts | overkill for this codebase |
| BSD-3 | similar to MIT plus advertising clause variants | adoption marginal vs MIT | no win over MIT |

## Consequences

- Anyone can use, modify, and redistribute, including commercially.
- We do not require contributors to sign a CLA; contributions are accepted under the project's existing MIT license per the standard inbound = outbound model.
- No patent grant. We do not believe this codebase implements anything patentable. If patent issues arise post-launch, we'd consider relicensing to Apache 2.0 with a major-version bump (MAJOR per semver).

## Notes

- `LICENSE` ships at repo root.
- Each source file does NOT need a per-file license header (project preference; `LICENSE` covers the whole repo).
- Third-party code (if any) is vendored under its own license terms in `vendor/<name>/LICENSE`.
