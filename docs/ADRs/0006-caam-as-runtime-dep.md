# ADR-0006 — caam as a runtime dependency

Date: 2026-04-27 · Status: accepted

## Context

`caam` ([Dicklesworthstone/coding_agent_account_manager](https://github.com/Dicklesworthstone/coding_agent_account_manager)) does the heavy lifting of profile isolation, token storage per profile, and provider invocation. Building all of that from scratch would duplicate ~5000 lines of Go, including the SQLite cooldown state machine and the per-profile filesystem isolation.

## Decision

**Require `caam` as an external runtime dependency**; do not vendor or rebuild it.

## Alternatives considered

| Option | Pro | Con | Verdict |
|---|---|---|---|
| (a) Require pre-install (chosen) | sovereign upstream; tracks improvements; minimal scope | one extra setup step | accepted |
| (b) Git submodule | versioning control | breaks `pip install`; submodule pain | rejected |
| (c) Reimplement minimal subset in Go/Rust | fewer deps | duplicates caam's evolution; supply-chain liability | rejected |
| (d) Bundle prebuilt caam binaries per OS | one-step install | binary distribution headache; signing keys; macOS notarisation | rejected for v1; reconsider at v1.x if friction proves real |

## Compatibility surface

ccpool's only contact with caam is via specific CLI commands. We pin the CLI shape:

| Command | Used for |
|---|---|
| `caam profile add <provider> <name> -d <desc>` | profile creation |
| `caam profile delete <provider> <name> --force` | rollback / migration |
| `caam env <provider> <name>` | resolve `CLAUDE_CONFIG_DIR` |
| `caam robot status <provider>` | profile health enumeration |
| `caam robot next <provider> --strategy smart` | tier-2 picker fallback |
| `caam robot precheck <provider> [--no-fetch]` | watcher-tick health peek |
| `caam robot act activate <provider> <name>` | rotate the active profile |
| `caam run <provider> --precheck --algorithm <a> --cooldown <c> --max-retries <r> -- <args...>` | wrapped invocation |

A version compatibility matrix lives in `docs/COMPATIBILITY.md`. Breaking changes upstream cause a doctor finding (`caam_version_too_old`) plus an integration test failure in CI.

## Consequences

- Install docs include "Install caam first" as step 1.
- Brew formula declares `depends_on "caam"` (a tap will be needed; alternatively, instructions to `go install` upstream).
- Mocked `caam` is the basis of the test suite (`tests/fixtures/bin/caam`).
- We track caam's release cadence; doctor warns at >2 upstream-minor-versions behind.
