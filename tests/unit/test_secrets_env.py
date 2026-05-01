"""Unit tests for ccpool.secrets in env-only mode.

These exercise the storage backend that is the cross-platform default once the
keychain / secret-tool path declines, and is forced on by CCPOOL_FORCE_ENV_STORAGE
(set by conftest.py for every test).
"""
from __future__ import annotations

import stat
import sys

import pytest


def _fresh():
    for mod in ("ccpool.paths", "ccpool.secrets"):
        sys.modules.pop(mod, None)
    from ccpool import secrets
    return secrets


def test_env_force_flag_active_via_conftest():
    secrets = _fresh()
    assert secrets.force_env() is True


def test_set_get_round_trip():
    secrets = _fresh()
    backend, err = secrets.set_token("alpha", "sk-ant-oat01-mock")
    assert backend == "env"
    assert err == ""
    assert secrets.get_token("alpha") == "sk-ant-oat01-mock"


def test_token_file_mode_0600():
    secrets = _fresh()
    secrets.set_token("alpha", "sk-ant-oat01-mock")
    p = secrets.env_file_path()
    mode = stat.S_IMODE(p.stat().st_mode)
    assert mode == (stat.S_IRUSR | stat.S_IWUSR), f"expected 0600, got {oct(mode)}"


def test_legacy_caam_prefix_read_compat(tmp_path):
    secrets = _fresh()
    p = secrets.env_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Pretend an older install wrote with the CAAM_TOKEN_ prefix.
    p.write_text("CAAM_TOKEN_alpha=legacy-token\n")
    assert secrets.get_token("alpha") == "legacy-token"


def test_invalid_profile_name_raises():
    secrets = _fresh()
    with pytest.raises(ValueError):
        secrets.set_token("../etc/passwd", "x")


def test_delete_removes_only_named_profile():
    secrets = _fresh()
    secrets.set_token("alpha", "tok-a")
    secrets.set_token("beta", "tok-b")
    removed = secrets.delete_token("alpha")
    assert "env" in removed
    assert secrets.get_token("alpha") is None
    assert secrets.get_token("beta") == "tok-b"


def test_storage_status_returns_native_backend_field():
    secrets = _fresh()
    secrets.set_token("alpha", "tok")
    status = secrets.storage_status()
    assert status["force_env"] is True
    assert "native_backend" in status
    assert "tokens" in status


def test_set_token_with_account_label_accepted():
    secrets = _fresh()
    backend, err = secrets.set_token("alpha", "tok", account="someone@example.com")
    assert backend == "env"
    assert err == ""


def test_no_personal_account_fallback(monkeypatch):
    """secrets.set_token must NOT silently invent a $USER if none is set —
    that's the bug-by-default we explicitly avoided.
    """
    monkeypatch.delenv("USER", raising=False)
    secrets = _fresh()
    # Env-only mode — the keychain code path is skipped, so this should still
    # succeed (it never asks for $USER).
    backend, err = secrets.set_token("alpha", "tok")
    assert backend == "env"
    assert err == ""


def test_user_required_for_keychain_account(monkeypatch):
    """If env-mode is OFF and we'd hit the keychain, $USER missing → RuntimeError.
    Defence: that path is the actual one with the bug-by-default risk.
    """
    secrets = _fresh()
    monkeypatch.delenv("USER", raising=False)
    with pytest.raises(RuntimeError, match=r"\$USER"):
        secrets._account_user()
