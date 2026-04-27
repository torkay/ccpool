"""Unit tests for cmaxctl.shell — managed-block install/remove/idempotency.

Covers: bashrc + zshrc + fish; legacy v0-block stripping; idempotent updates;
preservation of user content outside markers.
"""
from __future__ import annotations

import sys


def _fresh():
    for mod in ("cmaxctl.paths", "cmaxctl.config", "cmaxctl.shell"):
        sys.modules.pop(mod, None)
    from cmaxctl import config, shell
    return config, shell


def _make_cfg(config, files):
    cfg = config.Config()
    cfg.shell.manage_rc_file = True
    cfg.shell.files = files
    cfg.shell.alias_claude = True
    cfg.shell.export_flags = True
    return cfg


def test_install_skips_missing_files(tmp_path):
    config, shell = _fresh()
    rc = tmp_path / "absent.zshrc"
    cfg = _make_cfg(config, [str(rc)])
    log = shell.install(cfg)
    actions = [a for _, a in log]
    assert "skipped:no-file" in actions
    assert not rc.exists()


def test_install_writes_block_to_existing_file(tmp_path):
    config, shell = _fresh()
    rc = tmp_path / ".zshrc"
    rc.write_text("# user line one\nexport USER_THING=1\n")
    cfg = _make_cfg(config, [str(rc)])
    shell.install(cfg)
    text = rc.read_text()
    assert "user line one" in text
    assert shell.BEGIN_MARKER in text
    assert "alias claude='cmax'" in text
    assert "export CMAXCTL_USE_TOKEN=1" in text


def test_install_is_idempotent(tmp_path):
    config, shell = _fresh()
    rc = tmp_path / ".zshrc"
    rc.write_text("# user line\n")
    cfg = _make_cfg(config, [str(rc)])
    shell.install(cfg)
    first = rc.read_text()
    shell.install(cfg)
    second = rc.read_text()
    assert first == second
    # Block exactly once.
    assert second.count(shell.BEGIN_MARKER) == 1


def test_install_updates_existing_block_in_place(tmp_path):
    config, shell = _fresh()
    rc = tmp_path / ".zshrc"
    rc.write_text("# user line\n")
    cfg = _make_cfg(config, [str(rc)])
    shell.install(cfg)
    cfg.shell.alias_claude = False  # change something
    shell.install(cfg)
    text = rc.read_text()
    assert "alias claude='cmax'" not in text
    assert text.count(shell.BEGIN_MARKER) == 1


def test_remove_strips_block_and_preserves_user_lines(tmp_path):
    config, shell = _fresh()
    rc = tmp_path / ".zshrc"
    rc.write_text("# top\n")
    cfg = _make_cfg(config, [str(rc)])
    shell.install(cfg)
    shell.remove(cfg)
    text = rc.read_text()
    assert "# top" in text
    assert shell.BEGIN_MARKER not in text


def test_legacy_v0_block_stripped_on_install(tmp_path):
    """An older personal-substrate `cmax (Claude Max rotation)` block must be
    removed and replaced with the v1 block."""
    config, shell = _fresh()
    rc = tmp_path / ".zshrc"
    rc.write_text(
        "# user prelude\n"
        + shell.LEGACY_BEGIN_MARKERS[0] + "\n"
        + "alias claude='/old/path/cmax'\n"
        + shell.LEGACY_END_MARKERS[0] + "\n"
        + "# user epilogue\n"
    )
    cfg = _make_cfg(config, [str(rc)])
    shell.install(cfg)
    text = rc.read_text()
    assert shell.LEGACY_BEGIN_MARKERS[0] not in text
    assert "/old/path/cmax" not in text
    assert shell.BEGIN_MARKER in text
    assert "# user prelude" in text
    assert "# user epilogue" in text


def test_fish_conf_d_uses_fish_syntax(tmp_path, monkeypatch):
    config, shell = _fresh()
    fish = tmp_path / "fish" / "conf.d" / "cmaxctl.fish"
    cfg = _make_cfg(config, [str(fish)])
    shell.install(cfg)
    assert fish.exists()
    text = fish.read_text()
    assert "set -gx CMAXCTL_USE_TOKEN" in text
    assert "alias claude 'cmax'" in text  # fish-style: no '='
    assert "export CMAXCTL_USE_TOKEN" not in text


def test_disabled_manage_rc_file_is_a_noop(tmp_path):
    config, shell = _fresh()
    rc = tmp_path / ".zshrc"
    rc.write_text("# user\n")
    cfg = _make_cfg(config, [str(rc)])
    cfg.shell.manage_rc_file = False
    log = shell.install(cfg)
    assert log == []
    assert "cmaxctl" not in rc.read_text()
