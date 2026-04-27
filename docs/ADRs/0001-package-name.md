# ADR-0001 — Package name: `cmaxctl`

Date: 2026-04-27 · Status: accepted

## Context

The personal substrate this project derives from is named `cmax` (single-binary muscle memory: `cmax setup`, `cmax usage`). For a public release we need a name that is:
- available on PyPI, GitHub, Homebrew taps
- short
- recognisably about Claude Max
- doesn't collide with prior art

## Decision

- **Package name:** `cmaxctl`
- **CLI binary name:** `cmax` (shipped via `[project.scripts]` entry point inside the `cmaxctl` package, plus a `bin/cmax` bash dispatcher for richer subcommands)
- **GitHub repo:** `torkay/cmaxctl` at v1; migrate to org if/when contributors arrive
- **Homebrew tap:** `torkay/cmaxctl`

The kubectl model: package name carries the `ctl` suffix (as is conventional for control-plane CLIs: `kubectl`, `systemctl`, `etcdctl`), the day-to-day binary is the shorter form.

## Alternatives considered

| Name | PyPI | GitHub | Reason rejected |
|---|---|---|---|
| `cmax` | TAKEN (MIT 6.01 circuit simulator) | TAKEN (user account) | clash with established educational tool |
| `claudemax` | clean | TAKEN (user account) | naming half-clean only |
| `claude-orbit` | clean | clean | viable alternative; longer than needed |
| `claude-rotor` | clean | clean | viable alternative; less recognisable than `cmax*` |
| `crot` | clean | TAKEN | unfriendly abbreviation; partial collision |

## Consequences

- Operator's existing `cmax` muscle memory survives because the binary is still `cmax`.
- `pip install cmaxctl` is the canonical install verb; users may grep for the package by either name in docs.
- If a user has the MIT 6.01 `cmax` python package installed, our binary still works — they're on different namespaces (we install `cmax` as a separate script alongside whatever `cmax` python module exists).
- We retain `claudemax` and `claude-orbit` as fallback if `cmaxctl` somehow proves problematic post-launch.
