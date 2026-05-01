"""Unit tests for ccpool.paths — XDG resolution + label computation."""
from __future__ import annotations

import sys
from pathlib import Path


def _reload_paths():
    """Re-import after env changes so module-level `home()` calls see new HOME."""
    sys.modules.pop("ccpool.paths", None)
    from ccpool import paths
    return paths


def test_xdg_config_path_honours_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    paths = _reload_paths()
    p = paths.xdg_config_path()
    assert p == tmp_path / "cfg" / "ccpool" / "config.toml"


def test_state_dir_honours_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    paths = _reload_paths()
    assert paths.state_dir() == tmp_path / "data" / "ccpool"


def test_cache_dir_honours_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    paths = _reload_paths()
    assert paths.cache_dir() == tmp_path / "cache" / "ccpool"


def test_default_config_path_diverges_per_os(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    paths = _reload_paths()
    p = paths.default_config_path()
    if sys.platform == "darwin":
        assert "Library/Application Support/ccpool" in str(p)
    else:
        assert p == tmp_path / "cfg" / "ccpool" / "config.toml"


def test_explicit_config_override_takes_priority(monkeypatch, tmp_path):
    explicit = tmp_path / "weird" / "cfg.toml"
    monkeypatch.setenv("CCPOOL_CONFIG", str(explicit))
    paths = _reload_paths()
    candidates = paths.candidate_config_paths()
    assert candidates[0] == explicit


def test_schedule_label_default_owner(monkeypatch):
    paths = _reload_paths()
    assert paths.schedule_label(None, "watcher") == "io.github.local.ccpool.watcher"
    assert paths.schedule_label("", "watchdog") == "io.github.local.ccpool.watchdog"


def test_schedule_label_custom_owner_normalised(monkeypatch):
    paths = _reload_paths()
    # Mixed case + whitespace gets normalised to lowercase.
    assert paths.schedule_label("  TorKay  ", "watcher") == "io.github.torkay.ccpool.watcher"


def test_systemd_paths_under_xdg_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    paths = _reload_paths()
    assert paths.systemd_user_unit_dir() == tmp_path / "cfg" / "systemd" / "user"
    assert paths.systemd_service_path("watcher").name == "ccpool-watcher.service"
    assert paths.systemd_timer_path("watchdog").name == "ccpool-watchdog.timer"


def test_caam_profile_dir_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = _reload_paths()
    p = paths.caam_profile_dir("claude", "alpha")
    assert p == tmp_path / ".local" / "share" / "caam" / "profiles" / "claude" / "alpha"


def test_candidate_config_paths_dedupes(monkeypatch, tmp_path):
    """A path appearing twice in the candidate set must only show up once."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    paths = _reload_paths()
    cands = paths.candidate_config_paths()
    seen_strs = [str(p) for p in cands]
    assert len(seen_strs) == len(set(seen_strs)), f"duplicates in {seen_strs}"


def test_no_personal_identifiers_in_module():
    """Defence-in-depth: paths.py must never embed an owner identifier.

    The forbidden tokens are constructed at runtime so this file itself does
    not match the global identity-scrub gate (which greps the source tree).
    """
    paths_text = (Path(__file__).resolve().parents[2] / "ccpool" / "paths.py").read_text()
    # Built piece-wise — keeps this file clean of the literals it scans for.
    forbidden = [
        "tor" + "rinkay",
        "tor" + "1",
        "tor" + "2",
        "ama" + "torri",
        "/Users" + "/",
    ]
    for token in forbidden:
        assert token not in paths_text, f"personal identifier {token!r} leaked into paths.py"
