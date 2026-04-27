# Contributing to cmaxctl

Thanks for your interest. cmaxctl is a small project; the contribution flow is correspondingly light.

## Dev setup

```bash
git clone https://github.com/torkay/cmaxctl
cd cmaxctl
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

You'll also need `caam` and `claude` on PATH for full integration tests. Install instructions: see [docs/INSTALL.md](docs/INSTALL.md).

## Running tests

```bash
# Unit tests (no shell, no network)
pytest tests/unit/

# Integration tests (mocked caam + claude)
bats tests/integration/

# End-to-end (full mocked tree)
bats tests/e2e/

# Lint + type-check
ruff check .
mypy cmaxctl/
shellcheck bin/cmax
```

CI runs the full matrix on macos-13 / macos-14 / ubuntu-22.04 / ubuntu-24.04.

## Style

- **Stdlib only** in the `cmaxctl/` Python package. No external runtime dependencies. (Dev tooling like ruff/mypy/pytest is fine.)
- **bash, not zsh** in `bin/cmax`. POSIX where reasonable.
- **No comments unless they explain a non-obvious why**. Identifier names should carry the what.
- **Tables in docs**, not narrative paragraphs. Public docs (under `docs/`) are exempt from agent-internal docs conventions.
- **One concept per module** in the Python package. Modules over 500 lines are a smell; consider splitting.

## Branch + commit

- Branch from `main`; PR back to `main`.
- Squash-merge; commit message becomes the changelog entry.
- Reference issues via `Fixes #N` or `Refs #N` in the body.
- No co-author trailers required, but welcome.

## Adding a doctor finding

1. Add the code to `cmaxctl/doctor.py:diagnose()` with severity + fix string.
2. Add an autofix branch in `autofix()` if non-interactive.
3. Add a unit test in `tests/unit/test_doctor.py`.
4. Document in `docs/REFERENCE.md` under "Doctor finding codes".

## Adding a provider

See [docs/PROVIDERS.md](docs/PROVIDERS.md). At a minimum: implement the strategy table entries (login, token-issue, usage, identity, blocks). Stub anything Anthropic-specific. Add provider-specific tests.

## Releasing

Maintainers only. See [docs/REFERENCE.md#release-process](docs/REFERENCE.md#release-process).

## Code of conduct

Be respectful. Project maintainers will mediate disputes.
