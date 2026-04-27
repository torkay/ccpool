"""cmaxctl/pick.py — three-tier profile picker.

Tier 1: usage-aware via /api/oauth/usage (ground truth).
Tier 2: caam smart (cooldown + history heuristic).
Tier 3: deterministic round-robin via on-disk counter.

Saturation: when ALL profiles are above `cfg.picker.hard_threshold_pct`, the
caller refuses to spawn (better fail-fast than 429 mid-turn). Encoded as
`SATURATED_SENTINEL`.

Two public entry points:
    pick_env()              — returns env dict for the chosen profile (or None)
    pick_env_with_token()   — same plus injects CLAUDE_CODE_OAUTH_TOKEN

Stdlib only.
"""
from __future__ import annotations

import json
import sys

from cmaxctl import caam, config, paths, secrets, usage

SATURATED_SENTINEL = "__saturated__"


# ────────────────────────── degradation flags ──────────────────────────

def _set_degraded(reason: str) -> None:
    p = paths.degraded_flag_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(reason)
    except OSError:
        pass


def _set_saturated(detail: dict) -> None:
    p = paths.saturated_flag_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(detail, indent=2))
    except OSError:
        pass


def _clear_saturated() -> None:
    try:
        paths.saturated_flag_path().unlink(missing_ok=True)
    except OSError:
        pass


# ────────────────────────── round-robin counter ──────────────────────────

def _bump_counter() -> int:
    p = paths.watcher_counter_path()
    n = 0
    if p.exists():
        try:
            n = int(p.read_text().strip())
        except (ValueError, OSError):
            n = 0
    n += 1
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(n))
    except OSError:
        pass
    return n


# ────────────────────────── tier 1: usage-aware ──────────────────────────

def _usage_aware_pick(profiles: list[str], cfg: config.Config) -> str | None:
    """API-driven picker. Returns:
      - profile name (normal pick, possibly soft-saturated)
      - SATURATED_SENTINEL when ALL profiles ≥ hard threshold
      - None when ANY profile's usage endpoint is unreachable
        (caller falls through to tier 2)
    """
    snapshots = usage.fetch_all(profiles, cfg=cfg)
    pcts: dict[str, float] = {}
    for prof, u in snapshots.items():
        if u is None or u.five_hour is None:
            return None  # any-profile failure → fall through
        pcts[prof] = float(u.five_hour.utilization)

    if not pcts:
        return None

    chosen = min(pcts, key=lambda p: pcts[p])
    chosen_pct = pcts[chosen]
    soft = cfg.picker.soft_threshold_pct
    hard = cfg.picker.hard_threshold_pct

    if chosen_pct >= hard:
        _set_saturated({
            "all_above_hard_threshold_pct": hard,
            "snapshots": pcts,
            "action": "refuse_spawn",
        })
        return SATURATED_SENTINEL
    if chosen_pct >= soft:
        _set_saturated({
            "lowest_above_soft_threshold_pct": soft,
            "snapshots": pcts,
            "action": "advisory_notify",
        })
    else:
        _clear_saturated()
    return chosen


# ────────────────────────── tier 2 + 3: smart/RR ──────────────────────────

def _smart_pick(profiles: list[str], cfg: config.Config) -> str:
    """Walk the configured strategy_order. Returns a profile name, or
    SATURATED_SENTINEL if tier-1 reports all-above-hard."""
    for tier in cfg.picker.strategy_order:
        if tier == "usage_aware":
            chosen = _usage_aware_pick(profiles, cfg)
            if chosen == SATURATED_SENTINEL:
                return SATURATED_SENTINEL
            if chosen and chosen in profiles:
                return chosen
            continue
        if tier == "caam_smart":
            name = caam.caam_next(cfg, strategy="smart")
            if name and name in profiles:
                return name
            continue
        if tier == "round_robin":
            n = _bump_counter()
            return profiles[(n - 1) % len(profiles)]
    # Should never reach here; default to RR
    n = _bump_counter()
    return profiles[(n - 1) % len(profiles)]


# ────────────────────────── public API ──────────────────────────

def pick_env(cfg: config.Config | None = None) -> dict[str, str] | None:
    """Return env dict for the next picked profile, or None.

    Returns None when:
      - <2 healthy profiles
      - all profiles above hard threshold (caller refuses spawn)
      - caam env resolution fails
    """
    if cfg is None:
        cfg = config.load()
    profiles = caam.healthy_profiles(cfg)
    if len(profiles) < 2:
        return None
    chosen = _smart_pick(profiles, cfg)
    if chosen == SATURATED_SENTINEL:
        return None
    env = caam.caam_env_for(chosen, cfg)
    if not env:
        _set_degraded(f"caam env failed for {chosen}")
        return None
    env.setdefault("CMAXCTL_PROFILE", chosen)
    # Compat alias for orchestrators that read the legacy var
    env.setdefault("AGENT_FLEET_CAAM_PROFILE", chosen)
    return env


def pick_env_with_token(cfg: config.Config | None = None) -> dict[str, str] | None:
    """Like pick_env but injects CLAUDE_CODE_OAUTH_TOKEN from secrets.

    Returns None when:
      - <2 healthy profiles
      - caam env unavailable
      - no token stored for the chosen profile
    """
    if cfg is None:
        cfg = config.load()
    profiles = caam.healthy_profiles(cfg)
    if len(profiles) < 2:
        return None
    chosen = _smart_pick(profiles, cfg)
    if chosen == SATURATED_SENTINEL:
        return None
    env = caam.caam_env_for(chosen, cfg)
    if not env:
        _set_degraded(f"caam env failed for {chosen}")
        return None
    token = secrets.get_token(chosen)
    if not token:
        _set_degraded(f"no token for {chosen} — falling back to profile-only")
        return None
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    env.setdefault("CMAXCTL_PROFILE", chosen)
    env.setdefault("CMAXCTL_TOKEN_MODE", "1")
    env.setdefault("AGENT_FLEET_CAAM_PROFILE", chosen)
    env.setdefault("AGENT_FLEET_CAAM_TOKEN_MODE", "1")
    return env


# ────────────────────────── CLI ──────────────────────────

def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "profile"
    e = pick_env_with_token() if mode == "token" else pick_env()
    if e is None:
        print(json.dumps({"ok": False, "reason": "no_eligible_profile_or_token", "mode": mode}))
        return 1
    redacted = {k: ("<redacted>" if "TOKEN" in k else v) for k, v in e.items()}
    print(json.dumps({"ok": True, "mode": mode, "env": redacted}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
