"""cmaxctl/watchdog.py — daily health + usage tick.

Replaces the personal `cmax-watchdog.sh` bash script. Pure Python so Linux
gets it for free; thin bash shim at `bin/cmax-watchdog` exists only for
launchd/systemd ProgramArgument simplicity.

Each fire:
  1. Run doctor with auto-fix; capture machine output
  2. Prune stale caam backups
  3. Telegram-escalate doctor HIGH/CRITICAL findings
  4. Hit `cmax usage --json` and notify on threshold breach
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cmaxctl import caam, config, doctor, notify, paths, usage


def _log(line: str) -> None:
    p = paths.cache_dir() / "watchdog.log"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + line + "\n")
    except OSError:
        pass


def _trim_log() -> None:
    p = paths.cache_dir() / "watchdog.log"
    if not p.exists():
        return
    try:
        lines = p.read_text().splitlines()
        if len(lines) > 1000:
            p.write_text("\n".join(lines[-1000:]) + "\n")
    except OSError:
        pass


def tick(cfg: config.Config | None = None) -> int:
    """One watchdog fire. Returns 0 always."""
    if cfg is None:
        cfg = config.load()
    if not cfg.watchdog.enabled:
        return 0

    _log("watchdog tick")

    # 1. Doctor with autofix
    findings = doctor.diagnose(cfg)
    autofix_log = doctor.autofix(findings, cfg)
    for line in autofix_log:
        _log(f"autofix: {line}")
    findings = doctor.diagnose(cfg)  # re-diagnose
    severity = doctor.highest_severity(findings)
    _log(f"doctor severity: {severity}")

    if severity in ("HIGH", "CRITICAL"):
        msgs = [f"{f['code']}: {f['message']}" for f in findings
                if f.get("severity") in ("HIGH", "CRITICAL")]
        notify.fire(
            severity="high",
            title=f"cmaxctl watchdog: {severity}",
            message="\n".join(msgs)[:600] or f"watchdog detected {severity} findings",
            type_="cmaxctl-watchdog",
            cfg=cfg,
        )

    # 2. Prune
    n = doctor.prune_backups(keep_minutes=cfg.watchdog.prune_keep_minutes)
    _log(f"pruned {n} backups")

    # 3. Usage thresholds
    profiles = caam.healthy_profiles(cfg) or []
    if profiles:
        usages = usage.fetch_all(profiles, cfg=cfg)
        hits: list[str] = []
        for prof, u in usages.items():
            if u is None:
                continue
            five = u.five_hour.utilization if u.five_hour else None
            seven = u.seven_day.utilization if u.seven_day else None
            extra = u.extra_usage_pct
            if five is not None and five >= cfg.watchdog.five_hour_alert_pct:
                hits.append(f"{prof}: 5h util {five:.0f}% (cap soon)")
            if seven is not None and seven >= cfg.watchdog.seven_day_alert_pct:
                hits.append(f"{prof}: 7d util {seven:.0f}% (week burn)")
            if extra is not None and extra >= cfg.watchdog.extra_usage_alert_pct:
                used = u.extra_usage_used_dollars or 0.0
                limit = u.extra_usage_limit_dollars or 0.0
                cur = u.extra_usage_currency or ""
                hits.append(f"{prof}: PAYG {extra:.0f}% (${used:,.2f}/${limit:,.2f} {cur})")
        if hits:
            _log("usage thresholds breached")
            for h in hits:
                _log(f"  {h}")
            notify.fire(
                severity="high",
                title="cmaxctl usage: thresholds breached",
                message="\n".join(hits)[:600],
                type_="cmaxctl-usage",
                cfg=cfg,
            )

    _trim_log()
    return 0


def main() -> int:
    sys.exit(tick())


if __name__ == "__main__":
    main()
