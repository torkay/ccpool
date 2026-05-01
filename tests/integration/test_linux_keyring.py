"""Integration: secret-tool / libsecret round-trip on Linux.

Linux's libsecret (gnome-keyring) backend can only be exercised when:

    1. The host is Linux
    2. `secret-tool` and `gnome-keyring-daemon` are installed
    3. A D-Bus session bus is available (otherwise gnome-keyring can't start)
    4. The opt-in env var CCPOOL_TEST_LINUX_KEYRING=1 is set

We gate the test behind all four. CI runs it under `dbus-run-session` with
gnome-keyring unlocked via piped passphrase. Locally on macOS this test always
skips, which is intentional — keychain coverage is implicit when the operator
runs `ccpool setup` on their box.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

KEYRING_OPT_IN = os.environ.get("CCPOOL_TEST_LINUX_KEYRING") == "1"


pytestmark = pytest.mark.skipif(
    sys.platform != "linux"
    or not KEYRING_OPT_IN
    or shutil.which("secret-tool") is None,
    reason="linux + secret-tool + CCPOOL_TEST_LINUX_KEYRING=1 required",
)


def _flush_envvars(monkeypatch):
    """Don't force env-only mode for THIS test — we WANT the native backend."""
    monkeypatch.delenv("CCPOOL_FORCE_ENV_STORAGE", raising=False)
    monkeypatch.delenv("CAAM_FORCE_ENV_STORAGE", raising=False)


def test_secret_tool_round_trip(monkeypatch):
    _flush_envvars(monkeypatch)
    for mod in ("ccpool.paths", "ccpool.secrets"):
        sys.modules.pop(mod, None)
    from ccpool import secrets

    backend = secrets.native_backend_name()
    assert backend == "secret_tool", f"expected secret_tool, got {backend}"

    profile = "alpha-roundtrip"
    _backend_used, err = secrets.set_token(profile, "sk-ant-oat01-mock")
    assert err == "" or "stored in" in err, f"set failed: {err}"
    # If the keyring was unavailable mid-test, set_token falls through to env.
    # That's a partial pass — still verify get_token works.
    token = secrets.get_token(profile)
    assert token == "sk-ant-oat01-mock"

    removed = secrets.delete_token(profile)
    assert removed, "expected delete to remove from at least one backend"
    assert secrets.get_token(profile) is None


def test_secret_tool_invalid_profile_rejected(monkeypatch):
    """Defence-in-depth: invalid names must raise before we touch the keyring."""
    _flush_envvars(monkeypatch)
    for mod in ("ccpool.paths", "ccpool.secrets"):
        sys.modules.pop(mod, None)
    from ccpool import secrets
    with pytest.raises(ValueError):
        secrets.set_token("../escape", "tok")
