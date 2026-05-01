# ADR-0001 — Package name: `ccpool`

Date: 2026-04-27 · Status: accepted

## Context

The personal substrate this project derives from is named `ccpool` (single-binary muscle memory: `ccpool setup`, `ccpool usage`). For a public release we need a name that is:
- available on PyPI, GitHub, Homebrew taps
- short
- recognisably about Claude Max
- doesn't collide with prior art

## Decision

- **Package name:** `ccpool`
- **CLI binary name:** `ccpool` (shipped via `[project.scripts]` entry point inside the `ccpool` package, plus a `bin/ccpool` bash dispatcher for richer subcommands)
- **GitHub repo:** `torkay/ccpool` at v1; migrate to org if/when contributors arrive
- **Homebrew tap:** `torkay/ccpool`

The kubectl model: package name carries the `ctl` suffix (as is conventional for control-plane CLIs: `kubectl`, `systemctl`, `etcdctl`), the day-to-day binary is the shorter form.

## Alternatives considered

| Name | PyPI | GitHub | Reason rejected |
|---|---|---|---|
| `ccpool` | TAKEN (MIT 6.01 circuit simulator) | TAKEN (user account) | clash with established educational tool |
| `claudemax` | clean | TAKEN (user account) | naming half-clean only |
| `claude-orbit` | clean | clean | viable alternative; longer than needed |
| `claude-rotor` | clean | clean | viable alternative; less recognisable than `ccpool*` |
| `crot` | clean | TAKEN | unfriendly abbreviation; partial collision |

## Consequences

- Operator's existing `ccpool` muscle memory survives because the binary is still `ccpool`.
- `pip install ccpool` is the canonical install verb; users may grep for the package by either name in docs.
- If a user has the MIT 6.01 `ccpool` python package installed, our binary still works — they're on different namespaces (we install `ccpool` as a separate script alongside whatever `ccpool` python module exists).
- We retain `claudemax` and `claude-orbit` as fallback if `ccpool` somehow proves problematic post-launch.
