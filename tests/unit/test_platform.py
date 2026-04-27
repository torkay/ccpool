"""Unit tests for cmaxctl.platform — OS detection + scheduler dispatch.

The actual `launchctl load` / `systemctl --user` path can't be exercised in
unit tests (no daemon). We exercise:

  * OS / scheduler kind detection
  * launchd plist XML render
  * systemd unit file generation
  * cron line composition (under monkeypatched subprocess.run)
"""
from __future__ import annotations

import sys

import pytest


def _fresh():
    for mod in ("cmaxctl.paths", "cmaxctl.platform"):
        sys.modules.pop(mod, None)
    from cmaxctl import paths, platform
    return paths, platform


def test_os_detection_self_consistent():
    _, platform = _fresh()
    assert platform.is_macos() == (sys.platform == "darwin")
    assert platform.is_linux() == sys.platform.startswith("linux")
    assert platform.is_posix() is True  # macOS + Linux are both POSIX


def test_schedule_kind_returns_known_value():
    _, platform = _fresh()
    kind = platform.schedule_kind()
    assert kind in ("launchd", "systemd_user", "cron", "none")


def test_launchd_plist_render_well_formed():
    _, platform = _fresh()
    xml = platform._render_launchd_plist(
        "io.github.local.cmaxctl.watcher",
        ["/usr/bin/python3", "-m", "cmaxctl.watcher"],
        300,
    )
    # Schema-y assertions — content + structure.
    assert "<?xml version=" in xml
    assert "<key>Label</key>" in xml
    assert "io.github.local.cmaxctl.watcher" in xml
    assert "<integer>300</integer>" in xml
    # No unescaped ampersands / quotes.
    assert "<string>/usr/bin/python3</string>" in xml


def test_launchd_plist_escapes_special_chars():
    _, platform = _fresh()
    xml = platform._render_launchd_plist(
        "io.github.test.cmaxctl.watcher",
        ['/path/with "quote"', "arg<with>brackets"],
        60,
    )
    assert "&quot;" in xml
    assert "&lt;with&gt;brackets" in xml


def test_systemd_quote_handles_spaces():
    _, platform = _fresh()
    assert platform._systemd_quote("simple") == "simple"
    assert platform._systemd_quote("has space") == '"has space"'
    assert platform._systemd_quote('has "quote"') == '"has \\"quote\\""'


def test_cron_install_composes_marker_line(monkeypatch, tmp_path):
    """Mock crontab + capture the new content the install would write."""
    _, platform = _fresh()

    captured = {}

    def fake_run(cmd, **kw):
        if cmd == ["crontab", "-l"]:
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if cmd == ["crontab", "-"]:
            captured["input"] = kw.get("input", "")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError(f"unexpected: {cmd}")

    monkeypatch.setattr("subprocess.run", fake_run)
    ok, err = platform._cron_install(
        "watcher",
        ["/usr/bin/python3", "-m", "cmaxctl.watcher"],
        every_s=300,
    )
    assert ok and err == ""
    crontab = captured["input"]
    assert "# cmaxctl:watcher" in crontab
    assert "*/5 * * * *" in crontab
    assert "/usr/bin/python3" in crontab


def test_cron_watchdog_daily_schedule(monkeypatch):
    """every_s ≥ 86400 collapses to daily 04:30."""
    _, platform = _fresh()

    captured = {}

    def fake_run(cmd, **kw):
        if cmd == ["crontab", "-l"]:
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        if cmd == ["crontab", "-"]:
            captured["input"] = kw.get("input", "")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError

    monkeypatch.setattr("subprocess.run", fake_run)
    platform._cron_install(
        "watchdog",
        ["/usr/bin/python3", "-m", "cmaxctl.watchdog"],
        every_s=86400,
    )
    assert "30 4 * * *" in captured["input"]


def test_cron_install_dedupes_existing_marker(monkeypatch):
    """A second install must replace the prior marker-tagged line, not duplicate."""
    _, platform = _fresh()
    existing = "MAILTO=root\n*/2 * * * * /old/cmd  # cmaxctl:watcher\n"

    captured = {}

    def fake_run(cmd, **kw):
        if cmd == ["crontab", "-l"]:
            return type("R", (), {"returncode": 0, "stdout": existing, "stderr": ""})()
        if cmd == ["crontab", "-"]:
            captured["input"] = kw.get("input", "")
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        raise AssertionError

    monkeypatch.setattr("subprocess.run", fake_run)
    platform._cron_install("watcher", ["/new/cmd"], every_s=300)
    assert captured["input"].count("# cmaxctl:watcher") == 1
    assert "/new/cmd" in captured["input"]
    assert "/old/cmd" not in captured["input"]
    assert "MAILTO=root" in captured["input"]


@pytest.mark.skipif(sys.platform != "linux", reason="linux-only path")
def test_systemd_install_writes_unit_files(tmp_path, monkeypatch):
    paths, platform = _fresh()

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Block the actual systemctl invocation.
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )
    paths_mod = paths
    sys.modules["cmaxctl.paths"] = paths_mod
    ok, _err = platform._systemd_install(
        "watcher",
        paths_mod.systemd_service_path("watcher"),
        paths_mod.systemd_timer_path("watcher"),
        ["/usr/bin/python3", "-m", "cmaxctl.watcher"],
        300,
    )
    assert ok
    svc = paths_mod.systemd_service_path("watcher").read_text()
    assert "ExecStart=/usr/bin/python3 -m cmaxctl.watcher" in svc
    timer = paths_mod.systemd_timer_path("watcher").read_text()
    assert "OnUnitInactiveSec=300s" in timer
