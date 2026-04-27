"""cmaxctl/status.py — gather + render status dashboard.

`gather_status(cfg)` snapshots everything for `cmax status` / `cmax inventory`.
`render_status_human(s)` produces ANSI-coloured terminal output.
`render_status_json(s)` produces stable JSON for tooling.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from cmaxctl import caam, config, doctor, paths, platform, secrets

GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREY = "\033[90m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def _isatty() -> bool:
    return sys.stdout.isatty() and os.environ.get("CMAXCTL_NO_COLOR") != "1"


def _c(text: str, color: str) -> str:
    return f"{color}{text}{RESET}" if _isatty() else text


def gather_status(cfg: config.Config | None = None) -> dict[str, Any]:
    if cfg is None:
        cfg = config.load()

    profiles = caam.profile_summary(cfg)
    profile_rows = []
    for p in profiles:
        name = p.get("name") or "?"
        h = p.get("health")
        status = h.get("status") if isinstance(h, dict) else h
        token_present = bool(secrets.get_token(name)) if name != "?" else False
        age = doctor.token_age_days(name)
        profile_rows.append({
            "name": name,
            "account": p.get("account") or p.get("metadata", {}).get("account") or "",
            "health": status or "unknown",
            "active": p.get("active", False),
            "last_used": p.get("last_used") or p.get("last_used_at"),
            "token_present": token_present,
            "token_age_days": age,
        })

    return {
        "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "config_path": str(cfg.source_path) if cfg.source_path else None,
        "schema_version": cfg.meta.schema_version,
        "repo_owner": cfg.meta.repo_owner or paths.DEFAULT_OWNER,
        "caam_present": caam.caam_present(cfg),
        "schedule_kind": platform.schedule_kind(),
        "disabled": paths.disabled_flag_path().exists(),
        "profile_count": len(profile_rows),
        "profiles": profile_rows,
        "watcher_loaded": platform.schedule_status("watcher", cfg.meta.repo_owner),
        "watchdog_loaded": platform.schedule_status("watchdog", cfg.meta.repo_owner),
        "backup_count": doctor.count_backups(),
        "degraded": paths.degraded_flag_path().exists(),
        "degraded_reason": (
            paths.degraded_flag_path().read_text().strip()
            if paths.degraded_flag_path().exists() else None
        ),
        "saturated": paths.saturated_flag_path().exists(),
        "storage": secrets.storage_status(),
    }


def render_status_human(s: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(_c("cmaxctl status", BOLD))
    lines.append("")

    if s.get("disabled"):
        lines.append(_c("⚠  cmaxctl is DISABLED — `cmax enable` to re-enable", YELLOW))
        lines.append("")

    if not s.get("caam_present"):
        lines.append(_c("✗ caam binary not found on PATH", RED))
        return "\n".join(lines)

    if s["profile_count"] == 0:
        lines.append(_c("✗ 0 profiles configured — run `cmax setup`", RED))
    else:
        lines.append(_c(f"profiles ({s['profile_count']})", BOLD))
        for p in s["profiles"]:
            health = p["health"]
            health_c = (GREEN if health in ("healthy", "ok") else
                        YELLOW if health in ("cooldown", "expiring") else RED)
            tok_c = (GREEN if p["token_present"] else RED)
            age_c = GREEN
            age_str = "—"
            if p["token_age_days"] is not None:
                age_str = f"{p['token_age_days']}d"
                if p["token_age_days"] >= 360:
                    age_c = RED
                elif p["token_age_days"] >= 330:
                    age_c = YELLOW
            active_marker = _c(" ←active", GREEN) if p["active"] else ""
            lines.append(
                f"  {p['name']:14s} {_c(health, health_c):20s} "
                f"token: {_c('✓' if p['token_present'] else '✗', tok_c)} "
                f"age: {_c(age_str, age_c)}{active_marker}"
            )
    lines.append("")

    lines.append(_c("schedules", BOLD))
    lines.append(f"  primitive: {s.get('schedule_kind')}")
    lines.append(f"  watcher:   {_c('loaded' if s['watcher_loaded'] else 'inactive', GREEN if s['watcher_loaded'] else YELLOW)}")
    lines.append(f"  watchdog:  {_c('loaded' if s['watchdog_loaded'] else 'inactive', GREEN if s['watchdog_loaded'] else YELLOW)}")
    lines.append("")

    lines.append(_c("hygiene", BOLD))
    bc = YELLOW if s["backup_count"] > 50 else GREY
    lines.append(f"  caam backups: {_c(str(s['backup_count']), bc)}")
    if s.get("degraded"):
        lines.append(_c(f"  degradation flag SET — {s['degraded_reason']}", RED))
    if s.get("saturated"):
        lines.append(_c("  saturated flag SET — see `cmax usage` for details", YELLOW))
    lines.append("")

    storage = s.get("storage") or {}
    lines.append(_c("storage", BOLD))
    lines.append(f"  native backend: {storage.get('native_backend', '?')}")
    lines.append(f"  env file:       {storage.get('env_file', '?')} (exists: {storage.get('env_file_exists', False)})")
    if storage.get("force_env"):
        lines.append(_c("  CMAXCTL_FORCE_ENV_STORAGE=1 (force-env mode)", YELLOW))

    return "\n".join(lines)


def render_status_json(s: dict[str, Any]) -> str:
    return json.dumps(s, indent=2, default=str)
