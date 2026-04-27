"""Unit tests for cmaxctl.statusline — no-binary degraded path + emoji policy."""
from __future__ import annotations

import json
import sys


def _fresh():
    for mod in (
        "cmaxctl.paths", "cmaxctl.config", "cmaxctl.caam",
        "cmaxctl.usage", "cmaxctl.statusline",
    ):
        sys.modules.pop(mod, None)
    from cmaxctl import config, statusline
    return config, statusline


def test_snapshot_emits_required_fields_when_no_caam(monkeypatch):
    """Without caam on PATH the snapshot still returns valid JSON-shaped data."""
    monkeypatch.setenv("PATH", "/nonexistent")
    config, statusline = _fresh()
    cfg = config.Config()
    s = statusline.snapshot(cfg)
    assert s["version"] == 1
    assert s["profile"] is None
    assert s["five_hour_pct"] is None
    assert s["seven_day_pct"] is None
    assert s["saturated"] is False
    assert s["degraded"] is False
    assert s["emoji"] in ("⚪", "🔴", "🟡", "🟢")


def test_snapshot_serialisable_to_json(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    config, statusline = _fresh()
    s = statusline.snapshot(config.Config())
    blob = json.dumps(s)
    parsed = json.loads(blob)
    assert parsed == s


def test_emoji_thresholds_in_order(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    _, statusline = _fresh()
    assert statusline._emoji_for(50, False, False) == "🟢"
    assert statusline._emoji_for(80, False, False) == "🟢"
    assert statusline._emoji_for(85, False, False) == "🟡"
    assert statusline._emoji_for(95, False, False) == "🔴"
    assert statusline._emoji_for(50, True, False) == "🟡"
    assert statusline._emoji_for(50, False, True) == "🔴"
    assert statusline._emoji_for(None, False, False) == "⚪"


def test_render_short_handles_none_pct():
    _, statusline = _fresh()
    s = {"profile": None, "five_hour_pct": None, "emoji": "⚪"}
    out = statusline.render_short(s)
    assert "—" in out
    assert "%" not in out


def test_render_short_with_active_profile():
    _, statusline = _fresh()
    s = {"profile": "alpha", "five_hour_pct": 42.7, "emoji": "🟢"}
    out = statusline.render_short(s)
    assert "alpha" in out
    assert "43%" in out
