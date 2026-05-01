"""Unit tests for ccpool.statusline — no-binary degraded path + emoji policy."""
from __future__ import annotations

import json
import sys


def _fresh():
    for mod in (
        "ccpool.paths", "ccpool.config", "ccpool.caam",
        "ccpool.usage", "ccpool.statusline",
    ):
        sys.modules.pop(mod, None)
    from ccpool import config, statusline
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


def test_render_short_includes_seven_day_when_present():
    _, statusline = _fresh()
    s = {"profile": "alpha", "five_hour_pct": 42.7, "seven_day_pct": 71.5, "emoji": "🟢"}
    out = statusline.render_short(s)
    assert "alpha" in out
    assert "43%" in out
    assert "72%" in out
    assert " / " in out


def test_render_short_no_color_uses_text_marker():
    _, statusline = _fresh()
    s = {"profile": "alpha", "five_hour_pct": 42.7, "seven_day_pct": 71.5, "emoji": "🟢"}
    out = statusline.render_short(s, color=False)
    assert "OK" in out
    assert "🟢" not in out
    assert "alpha" in out
    assert "43%" in out


def test_render_short_no_color_text_markers_for_each_state():
    _, statusline = _fresh()
    base = {"profile": "p", "five_hour_pct": 50.0, "seven_day_pct": 50.0}
    assert statusline.render_short({**base, "emoji": "🟢"}, color=False).startswith("OK")
    assert statusline.render_short({**base, "emoji": "🟡"}, color=False).startswith("WARN")
    assert statusline.render_short({**base, "emoji": "🔴"}, color=False).startswith("SAT")
    assert statusline.render_short({**base, "emoji": "⚪"}, color=False).startswith("DEG")


def test_render_format_placeholders():
    _, statusline = _fresh()
    s = {"profile": "alpha", "five_hour_pct": 42.0, "seven_day_pct": 71.5,
         "emoji": "🟢", "saturated": False, "degraded": False}
    assert statusline.render_format(s, "{marker} {profile} {five}/{seven}") == "OK alpha 42%/72%"
    assert statusline.render_format(s, "{emoji} {profile}") == "🟢 alpha"
    assert statusline.render_format(s, "sat={saturated} deg={degraded}") == "sat=no deg=no"


def test_render_format_handles_null_pct():
    _, statusline = _fresh()
    s = {"profile": None, "five_hour_pct": None, "seven_day_pct": None,
         "emoji": "⚪", "saturated": False, "degraded": True}
    assert statusline.render_format(s, "{marker} {profile} {five}/{seven}") == "DEG — —/—"


def test_parse_args_combinations():
    _, statusline = _fresh()
    assert statusline._parse_args([]) == (False, True, None)
    assert statusline._parse_args(["--short"]) == (True, True, None)
    assert statusline._parse_args(["--no-color"]) == (True, False, None)
    assert statusline._parse_args(["--format={profile}"]) == (False, True, "{profile}")
