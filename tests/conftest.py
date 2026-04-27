"""Shared pytest fixtures for cmaxctl tests.

Pinned guarantees:

* Tests NEVER touch the operator's real $HOME — every test sees a temp HOME
  with isolated XDG dirs.
* The native secret backend is forced OFF unless a test explicitly opts in
  by clearing CMAXCTL_FORCE_ENV_STORAGE — this prevents tests poking real
  Keychain / libsecret entries.
* Mock `caam` and `claude` binaries from tests/fixtures/bin/ are NOT on PATH
  by default; opt in with the `mock_bins_on_path` fixture.

Stdlib + pytest only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

FIXTURES_BIN = Path(__file__).parent / "fixtures" / "bin"


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path, monkeypatch):
    """Reroute $HOME + XDG paths to a temp tree per test."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USER", "tester")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    # Force env-only secret backend so tests never poke a real keyring.
    monkeypatch.setenv("CMAXCTL_FORCE_ENV_STORAGE", "1")
    # Re-import path-sensitive modules so they pick up the new HOME.
    for mod in [
        "cmaxctl.paths", "cmaxctl.config", "cmaxctl.secrets",
        "cmaxctl.shell", "cmaxctl.platform",
    ]:
        sys.modules.pop(mod, None)
    yield


@pytest.fixture
def mock_bins_on_path(monkeypatch):
    """Prepend tests/fixtures/bin/ to PATH so caam/claude resolve to mocks."""
    monkeypatch.setenv("PATH", f"{FIXTURES_BIN}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CMAX_MOCK_CAAM_DIR", os.environ["XDG_DATA_HOME"] + "/caam")
    yield FIXTURES_BIN


@pytest.fixture
def is_linux_only():
    """Skip the test if not on Linux."""
    if sys.platform != "linux":
        pytest.skip("linux-only test")


@pytest.fixture
def is_macos_only():
    if sys.platform != "darwin":
        pytest.skip("macos-only test")
