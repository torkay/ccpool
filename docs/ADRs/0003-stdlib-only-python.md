# ADR-0003 — Python: stdlib only at runtime

Date: 2026-04-27 · Status: accepted

## Context

Most CLI tooling on PyPI pulls in 5-50 transitive dependencies. Each of those is a supply-chain attack surface, an upgrade-pin headache, and a Python-version compatibility risk. Our hot-path code does HTTP (1 endpoint), file I/O, subprocess invocation, and JSON parsing — all in stdlib.

## Decision

The `cmaxctl/` runtime package depends ONLY on the Python stdlib (Python 3.11+).

Test/dev dependencies (`pytest`, `ruff`, `mypy`, `build`) are allowed under `[project.optional-dependencies].dev`.

## Constraints this imposes

| Want | Stdlib equivalent |
|---|---|
| HTTP client | `urllib.request` |
| TOML config | `tomllib` (stdlib since 3.11) |
| JSON | `json` |
| Subprocess | `subprocess` |
| Concurrency | `concurrent.futures` (already used in `usage.py:fetch_all`) |
| Path manipulation | `pathlib` |
| Argparse | `argparse` |
| TOML *writing* | hand-rolled (we already do this in cmax_lib for the zshrc managed block; trivial here too) |

## Alternatives considered

| Choice | Pro | Con |
|---|---|---|
| Add `requests` | nicer HTTP DSL | one dep → 5 transitive; no real win for one endpoint |
| Add `pydantic` | nice config validation | one big dep → 10+ transitive; we own validation already |
| Add `click` for CLI | nicer DX | argparse is fine; cmax is mostly a thin shell over the bash dispatcher |
| Add `httpx` | async + http2 | overkill; no use for either feature |

## Consequences

- Cold-start is fast (~50ms for `cmax usage`).
- No supply-chain attack surface beyond Python itself + `caam` (separately verified).
- We hand-roll TOML *writing* and CLI argparse — accepting modest verbosity for zero deps.
- Future maintainers cannot reach for `requests` etc without a new ADR overriding this one.
