"""Unit tests for ccpool.migrate.detect_v0 — fresh container reports no v0."""
from __future__ import annotations

import sys


def _fresh():
    for mod in ("ccpool.paths", "ccpool.config", "ccpool.caam",
                "ccpool.secrets", "ccpool.shell", "ccpool.migrate"):
        sys.modules.pop(mod, None)
    from ccpool import migrate
    return migrate


def test_detect_v0_on_clean_home_reports_nothing(monkeypatch):
    """A fresh container with no caam profiles, no plists, no zshrc block →
    detected=False."""
    migrate = _fresh()
    d = migrate.detect_v0()
    assert d.detected is False
    assert d.signals == []
    assert d.profiles == []
    assert d.legacy_plists == []
    assert d.legacy_zshrc_blocks == []


def test_detect_v0_picks_up_legacy_zshrc_block(tmp_path, monkeypatch):
    """A zshrc with the v0 marker counts as one signal — but one signal alone
    is below the detection threshold (≥2)."""
    migrate = _fresh()
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    # NB: this is the v0 (personal-substrate) marker that migrate.py detects.
    # The literal must stay as `cmax` because that's what existed in the wild
    # before ccpool. The renamer must not rewrite this.
    (home / ".zshrc").write_text(
        "# user line\n"
        "# >>> cmax (Claude Max rotation)\n"
        "alias claude='cmax'\n"
        "# <<< cmax\n"
    )
    migrate = _fresh()
    d = migrate.detect_v0()
    assert any("legacy zshrc" in s for s in d.signals)
    # 1 signal alone shouldn't trip detected (threshold is ≥2).
    assert d.detected is False


def test_synthesize_config_from_v0_uses_observed_profiles(monkeypatch):
    migrate = _fresh()
    d = migrate.V0Detection(
        detected=True,
        signals=["x"],
        profiles=["alpha", "beta"],
        legacy_plists=[],
        legacy_zshrc_blocks=[],
    )
    cfg = migrate.synthesize_config_from_v0(d, repo_owner="torkay")
    assert cfg.meta.repo_owner == "torkay"
    assert [p.name for p in cfg.profiles] == ["alpha", "beta"]
    # No leaked email when no tokens.json on disk.
    assert all(p.email == "" for p in cfg.profiles)
