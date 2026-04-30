# Contributing to cmaxctl

PRs and issues welcome. This file covers the dev loop, style expectations, and how to ship a release.

## Dev setup

```bash
git clone https://github.com/torkay/cmaxctl
cd cmaxctl
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
```

`[dev]` pulls in `pytest`, `ruff`, `pyyaml` (workflow validation only — not a runtime dep). The runtime itself is stdlib-only ([ADR-0003](docs/ADRs/0003-stdlib-only-python.md)).

You'll also want:

```bash
brew install bats-core         # for integration tests
brew install caam              # or: go install github.com/Dicklesworthstone/coding_agent_account_manager/cmd/caam@latest
brew install claude            # or follow Anthropic's install guide
```

The integration tests use mocked `caam` and `claude` binaries (`tests/fixtures/bin/`) so you don't need real ones to run the suite. But you do need them for end-to-end smoke testing of your changes.

## Running tests

```bash
pytest tests/unit tests/integration -v        # unit + integration
bats tests/integration tests/e2e              # bash-side integration + e2e
ruff check cmaxctl tests                      # lint
```

The full test matrix runs on push (see `.github/workflows/{linux,macos}.yml`). Locally, the macOS path is what most contributors will hit; for Linux validation:

```bash
./install/linux/run-tests-in-docker.sh         # builds + runs in Ubuntu container
```

## Style

- **Python**: stdlib-only (no `requests`, `pydantic`, etc.). Single-file modules where possible. `ruff check --fix` is your friend.
- **Bash**: stay POSIX-compatible enough that `bash 3.2` (macOS default) works. Avoid bashisms in `bin/cmax`.
- **Identity scrub**: NEVER commit a personal identifier (your username, email, etc.). The CI `identity-scrub` job hard-fails on a hit; if you tripped it, see the error message for the specific file:line.
- **Comments**: write them only when the WHY is non-obvious. The CI doesn't enforce this but reviewers will trim them.
- **Tests**: every new finding code in `doctor.py` needs a unit test. Every new subcommand in `bin/cmax` needs a bats case.
- **No SQLite, no resident daemon, no node tooling.** These are deliberate (see ADRs).

## Adding a feature

1. **Open an issue first** for anything bigger than a one-line fix. Saves rework if the design needs to land somewhere different.
2. **Branch off `main`.** PRs target `main`; squash-merge keeps history linear.
3. **Add a CHANGELOG entry** under `[Unreleased]` (Keep-a-Changelog format).
4. **Add tests** at the appropriate level (unit if it's pure-function; integration/bats if it crosses the python↔bash boundary).
5. **Run the gate locally** before opening the PR:
   ```bash
   pytest tests/unit tests/integration -q
   bats tests/integration tests/e2e
   ruff check cmaxctl tests
   ```

## Adding a doctor finding

1. Add the finding to `cmaxctl/doctor.py` with a stable code (`snake_case`).
2. Document it in `docs/REFERENCE.md` (severity + auto-fix table) and `docs/TROUBLESHOOTING.md` (symptom-indexed entry).
3. Add a unit test in `tests/unit/test_doctor.py`.
4. If there's an auto-fix, the test must verify idempotency (running fix twice produces the same state).

## Adding a provider

See [docs/PROVIDERS.md § Adding a new provider](docs/PROVIDERS.md#adding-a-new-provider).

## Cutting a release

Releases are gated on three lanes being green: macOS CI, Linux CI, identity-scrub.

1. **Update CHANGELOG.md.** Move `[Unreleased]` items into a new `[X.Y.Z]` section with the date.
2. **Bump `cmaxctl/_version.py`.** The release workflow verifies the tag matches the file.
3. **Commit + tag.** Use signed tags via OIDC; never commit a GPG key.
   ```bash
   git commit -am "Release X.Y.Z"
   git tag -s vX.Y.Z -m "vX.Y.Z"
   git push origin main vX.Y.Z
   ```
4. **CI takes over.** `release.yml` builds sdist + wheel, publishes to PyPI via OIDC trusted publishing, creates the GitHub release with auto-changelog, and triggers the Homebrew formula bump.
5. **Verify on a clean VM.** `pip install cmaxctl --user; cmax doctor` should be green on a fresh macOS + a fresh Ubuntu.

Semver:

| Bump | When |
|---|---|
| MAJOR | `config.toml` schema break · path layout break · install path break |
| MINOR | new subcommand · new provider · new doctor finding · new platform |
| PATCH | bug fix · doc fix · doctor message wording · internal refactor |

## Reporting a security issue

See [SECURITY.md](SECURITY.md). Please don't file security issues in public GitHub issues.

## Code of conduct

Be excellent. Don't be an asshole. We follow the spirit of the [Contributor Covenant](https://www.contributor-covenant.org/) without ceremoniously adopting it as a separate file.

## License

MIT — see [LICENSE](LICENSE). Contributions are accepted under the same terms.
