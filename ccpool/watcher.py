"""ccpool/watcher.py — proactive rotation tick.

Runs as a launchd StartInterval / systemd-user timer (default 300s). No daemon,
no threads. Each fire takes ~50ms locally; network only every Nth cycle.

Algorithm:
  1. Cheap local read (`caam robot precheck --no-fetch`). Short-circuit unless
     ≥2 profiles, ≥1 healthy, active set, recommended != active and healthy.
  2. Every Nth fire: re-run precheck WITH network fetch.
  3. On qualified rotation, call `caam robot act activate` and notify.

Refuses to rotate when: caam absent, <2 profiles, 0 healthy, active null,
recommended unhealthy, or within MIN_GAP_S of last rotation.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any

from ccpool import caam, config, notify, paths

HEALTHY = {"healthy", "ok"}


# ────────────────────────── log + counter ──────────────────────────

def _emit(event: str, **fields) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}
    p = paths.watcher_log_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


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


def _last_rotate_age_s() -> float:
    p = paths.watcher_last_rotate_path()
    if not p.exists():
        return float("inf")
    try:
        return time.time() - p.stat().st_mtime
    except OSError:
        return float("inf")


def _mark_rotated() -> None:
    p = paths.watcher_last_rotate_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
    except OSError:
        pass


# ────────────────────────── recommendation parsing ──────────────────────────

def _get_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return (
            value.get("name")
            or (value.get("profile") or {}).get("name")
            or value.get("recommended_profile")
        )
    return None


def _get_health(value: Any) -> str | None:
    if isinstance(value, dict):
        h = value.get("health")
        if isinstance(h, dict):
            return h.get("status")
        return h
    return None


# ────────────────────────── main tick ──────────────────────────

def tick(cfg: config.Config | None = None) -> int:
    """One watcher fire. Returns 0 always (launchd shouldn't see failures)."""
    if cfg is None:
        cfg = config.load()
    if not cfg.watcher.enabled:
        return 0
    if not caam.caam_present(cfg):
        return 0

    fire_n = _bump_counter()
    use_network = fire_n % cfg.watcher.network_every_n == 0

    status = caam.caam_status(cfg)
    if not status or not status.get("success"):
        return 0
    summary = (status.get("data") or {}).get("summary") or {}
    if (summary.get("total_profiles") or 0) < 2:
        return 0
    if (summary.get("healthy_profiles") or 0) < 1:
        _emit("not_ready", reason="no_healthy_profiles", fire=fire_n)
        return 0

    if _last_rotate_age_s() < cfg.watcher.min_gap_s:
        _emit("flap_guard", fire=fire_n)
        return 0

    precheck = caam.caam_precheck(cfg, no_fetch=not use_network)
    if not precheck or not precheck.get("success"):
        return 0

    data = precheck.get("data") or {}
    recommended = data.get("recommended")
    rec_name = _get_name(recommended)
    rec_health = _get_health(recommended)

    active = None
    for p in (status.get("data") or {}).get("providers", [{}])[0].get("profiles", []):
        if isinstance(p, dict) and p.get("active"):
            active = p.get("name")
            break

    if not rec_name or not active:
        _emit("incomplete_state", fire=fire_n, rec=rec_name, active=active)
        return 0
    if rec_name == active:
        _emit("steady", active=active, fire=fire_n, networked=use_network)
        return 0
    if rec_health not in HEALTHY:
        _emit("rec_unhealthy", rec=rec_name, rec_health=rec_health,
              active=active, fire=fire_n)
        return 0

    if cfg.watcher.dry_run:
        _emit("would_rotate", from_=active, to=rec_name, fire=fire_n)
        return 0

    if caam.caam_activate(rec_name, cfg):
        _mark_rotated()
        _emit("rotated", from_=active, to=rec_name, fire=fire_n,
              networked=use_network)
        notify.fire(
            severity="info" if "info" in cfg.notify.severities else "high",
            title=f"ccpool: rotated {active} → {rec_name}",
            message=f"fire #{fire_n}, networked={use_network}",
            type_="ccpool-watcher",
            cfg=cfg,
        )
    else:
        _emit("rotate_failed", from_=active, to=rec_name, fire=fire_n)

    return 0


def main() -> int:
    sys.exit(tick())


if __name__ == "__main__":
    main()
