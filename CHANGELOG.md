# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public scaffolding (Phase 0): repo skeleton, pyproject, LICENSE, scaffolding for python package, bash dispatcher, install scripts, ADRs.
- ADR-0001 (package-name), ADR-0002 (license-mit), ADR-0003 (stdlib-only-python), ADR-0004 (no-resident-daemon), ADR-0005 (keychain-then-env-fallback), ADR-0006 (caam-as-runtime-dep), ADR-0007 (oauth-usage-undocumented-endpoint), ADR-0008 (token-storage-encryption-stance), ADR-0009 (telemetry-opt-in), ADR-0010 (no-mid-turn-rotation).
- Phase 2 (Linux full parity): `tests/fixtures/bin/{caam,claude}` mock harness; 47 unit tests across paths/config/secrets/shell/platform/identity/statusline/migrate; 6 integration tests for the no-binary degraded path; libsecret round-trip test gated on `CCPOOL_TEST_LINUX_KEYRING=1`; `install/linux/Dockerfile.test` + `run-tests-in-docker.sh` for local Linux validation from macOS; `.github/workflows/linux.yml` matrix (ubuntu-22.04/24.04 × py 3.11/3.12) with separate `keyring`, `identity-scrub`, and `package` jobs; `docs/COMPATIBILITY.md` with tier-1/2/3 distro matrix.
- Phase 3 (tests + CI + docs): 33 bats integration cases across `test_dispatcher.bats`, `test_subcommand_passthrough.bats`, `test_disable_enable.bats`, `test_status_render.bats`, `test_doctor_fix.bats`, `test_rotate.bats`, and e2e `test_first_run.bats`; shared `tests/integration/test_helper.bash` with HOME/XDG isolation and config + caam-profile + token seeders; `.github/workflows/macos.yml` (macos-13/14 × py 3.11/3.12/3.13 minus py3.13 on macos-13) with unit/integration/bats lanes + identity-scrub + package; `.github/workflows/release.yml` (tag-trigger build → PyPI OIDC publish → GitHub release with auto-changelog → Homebrew formula bump); `.github/workflows/codeql.yml` (weekly + on-PR Python security analysis); docs filler — `INSTALL.md`, `REFERENCE.md`, `ARCHITECTURE.md` (with sequence diagrams for setup + pick), `THREAT_MODEL.md`, `PROVIDERS.md`, `TROUBLESHOOTING.md` (symptom-indexed); README 30-second demo; CONTRIBUTING.md tightened with the dev-loop and release flow.

### Fixed
- Mock caam binary now creates `.credentials.json` under the production-correct `<profile>/xdg_config/claude-code/` path (was at the profile root). Aligns the mock with `ccpool.paths.caam_profile_creds_path`.

### Notes
- v1.0.0 will tag when the test matrix is green on macos-13/14 + ubuntu-22/24 and the three install paths verify on clean VMs.
