"""cmaxctl/statusline.py — one-line JSON for prompt integrations.

Designed for Starship `[custom.cmax]`, oh-my-zsh segments, p10k, etc.

`cmax statusline`            # JSON
`cmax statusline --short`    # short text (active profile + emoji)
`cmax statusline --no-color` # plain text variant
"""
from __future__ import annotations

import json
import sys

from cmaxctl import caam, config, paths, usage


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
    if pct >= 60:
        return "🟢"
    return "🟢"


def snapshot(cfg: config.Config | None = None) -> dict:
    """Build the statusline payload."""
    if cfg is None:
        cfg = config.load()

    # Active profile (caam reports it)
    active: str | None = None
    data = caam.caam_status(cfg)
    for p in (data.get("data") or {}).get("providers", [{}])[0].get("profiles", []):
        if isinstance(p, dict) and p.get("active"):
            active = p.get("name")
            break

    # Best snapshot we can get cheaply
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


def render_short(s: dict) -> str:
    profile = s.get("profile") or "—"
    pct = s.get("five_hour_pct")
    pct_str = f" {pct:.0f}%" if pct is not None else ""
    return f"{s['emoji']} {profile}{pct_str}"


def main() -> int:
    cfg = config.load()
    s = snapshot(cfg)
    if "--short" in sys.argv:
        print(render_short(s))
    else:
        print(json.dumps(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
