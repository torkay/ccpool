"""ccpool/statusline.py — one-line JSON for prompt integrations.

Designed for Starship `[custom.ccpool]`, oh-my-zsh segments, p10k, tmux.

`ccpool statusline`                 # JSON
`ccpool statusline --short`         # text (emoji + profile + 5h/7d pct)
`ccpool statusline --no-color`      # text without emoji, ascii marker instead
`ccpool statusline --format=...`    # custom template
"""
from __future__ import annotations

import json
import sys

from ccpool import caam, config, paths, usage

_TEXT_MARKERS = {
    "🟢": "OK",
    "🟡": "WARN",
    "🔴": "SAT",
    "⚪": "DEG",
}


def _emoji_for(pct: float | None, saturated: bool, degraded: bool) -> str:
    if degraded:
        return "🔴"
    if saturated:
        return "🟡"
    if pct is None:
        return "⚪"
    if pct >= 95:
        return "🔴"
    if pct >= 85:
        return "🟡"
    return "🟢"


def snapshot(cfg: config.Config | None = None) -> dict:
    """Build the statusline payload."""
    if cfg is None:
        cfg = config.load()

    active: str | None = None
    data = caam.caam_status(cfg)
    for p in (data.get("data") or {}).get("providers", [{}])[0].get("profiles", []):
        if isinstance(p, dict) and p.get("active"):
            active = p.get("name")
            break

    five = seven = None
    if active:
        u = usage.fetch(active, cfg=cfg)
        if u:
            five = u.five_hour.utilization if u.five_hour else None
            seven = u.seven_day.utilization if u.seven_day else None

    saturated = paths.saturated_flag_path().exists()
    degraded = paths.degraded_flag_path().exists()

    return {
        "version": 1,
        "profile": active,
        "five_hour_pct": five,
        "seven_day_pct": seven,
        "saturated": saturated,
        "degraded": degraded,
        "emoji": _emoji_for(five, saturated, degraded),
    }


def render_short(s: dict, *, color: bool = True) -> str:
    profile = s.get("profile") or "—"
    five = s.get("five_hour_pct")
    seven = s.get("seven_day_pct")
    emoji = s.get("emoji", "⚪")
    marker = emoji if color else _TEXT_MARKERS.get(emoji, "DEG")
    if five is None and seven is None:
        return f"{marker} {profile}"
    parts = []
    if five is not None:
        parts.append(f"{five:.0f}%")
    if seven is not None:
        parts.append(f"{seven:.0f}%")
    return f"{marker} {profile} {' / '.join(parts)}"


def render_format(s: dict, fmt: str) -> str:
    """Render a user-supplied template.

    Placeholders: {emoji} {marker} {profile} {five} {seven} {saturated} {degraded}.
    {five} and {seven} render as `42%` or `—` when null.
    {saturated} and {degraded} render as `yes`/`no`.
    """
    def pct(v: float | None) -> str:
        return f"{v:.0f}%" if v is not None else "—"

    emoji = s.get("emoji", "")
    return fmt.format(
        emoji=emoji,
        marker=_TEXT_MARKERS.get(emoji, ""),
        profile=s.get("profile") or "—",
        five=pct(s.get("five_hour_pct")),
        seven=pct(s.get("seven_day_pct")),
        saturated="yes" if s.get("saturated") else "no",
        degraded="yes" if s.get("degraded") else "no",
    )


def _parse_args(argv: list[str]) -> tuple[bool, bool, str | None]:
    short = False
    color = True
    fmt: str | None = None
    for a in argv:
        if a == "--short":
            short = True
        elif a == "--no-color":
            color = False
            short = True
        elif a.startswith("--format="):
            fmt = a.split("=", 1)[1]
    return short, color, fmt


def main() -> int:
    cfg = config.load()
    s = snapshot(cfg)
    short, color, fmt = _parse_args(sys.argv[1:])
    if fmt is not None:
        print(render_format(s, fmt))
    elif short:
        print(render_short(s, color=color))
    else:
        print(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
