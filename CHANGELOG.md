# Changelog

All notable changes to this project will be documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial public scaffolding (Phase 0): repo skeleton, pyproject, LICENSE, scaffolding for python package, bash dispatcher, install scripts, ADRs.
- ADR-0001 (package-name), ADR-0002 (license-mit), ADR-0003 (stdlib-only-python), ADR-0004 (no-resident-daemon), ADR-0005 (keychain-then-env-fallback), ADR-0006 (caam-as-runtime-dep), ADR-0007 (oauth-usage-undocumented-endpoint), ADR-0008 (token-storage-encryption-stance), ADR-0009 (telemetry-opt-in), ADR-0010 (no-mid-turn-rotation).
- Phase 2 (Linux full parity): `tests/fixtures/bin/{caam,claude}` mock harness; 47 unit tests across paths/config/secrets/shell/platform/identity/statusline/migrate; 6 integration tests for the no-binary degraded path; libsecret round-trip test gated on `CMAXCTL_TEST_LINUX_KEYRING=1`; `install/linux/Dockerfile.test` + `run-tests-in-docker.sh` for local Linux validation from macOS; `.github/workflows/linux.yml` matrix (ubuntu-22.04/24.04 × py 3.11/3.12) with separate `keyring`, `identity-scrub`, and `package` jobs; `docs/COMPATIBILITY.md` with tier-1/2/3 distro matrix.

### Notes
- v1.0.0 will tag when the test matrix is green on macos-13/14 + ubuntu-22/24 and the three install paths verify on clean VMs.
