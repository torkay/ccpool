"""cmaxctl/doctor.py — diagnostic findings + auto-fix.

Severity levels: CRITICAL > HIGH > MEDIUM > LOW.

Findings are dicts: {severity, code, message, fix}.

`diagnose(cfg)` enumerates current state and returns findings.
`autofix(findings, cfg)` applies the non-interactive fixes; returns log lines.
`prune_backups(keep_minutes)` cleans caam .json backups.
"""
from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path
from typing import Any

from cmaxctl import caam, config, paths, platform, secrets

BACKUP_DIR = Path.home() / ".claude" / "backups"
BACKUP_GLOB = ".claude.json.backup.*"

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


# ────────────────────────── helpers ──────────────────────────

def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def count_backups() -> int:
    if not BACKUP_DIR.exists():
        return 0
    try:
        return sum(1 for _ in BACKUP_DIR.glob(BACKUP_GLOB))
    except OSError:
        return 0


def prune_backups(keep_minutes: int = 1440) -> int:
    if not BACKUP_DIR.exists():
        return 0
    cutoff = _utc_now().timestamp() - keep_minutes * 60
    n = 0
    for p in BACKUP_DIR.glob(BACKUP_GLOB):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                n += 1
        except OSError:
            continue
    return n


def highest_severity(findings: list[dict[str, Any]]) -> str | None:
    sev = max((SEVERITY_RANK.get(f.get("severity", ""), 0) for f in findings), default=0)
    if sev == 0:
        return None
    for k, v in SEVERITY_RANK.items():
        if v == sev:
            return k
    return None


# ────────────────────────── token age ──────────────────────────

def _read_tokens_json() -> dict[str, dict[str, str]]:
    import json
    p = paths.tokens_json_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def token_age_days(profile: str) -> int | None:
    rec = _read_tokens_json().get(profile)
    if not rec:
        return None
    issued_str = rec.get("issued_at", "")
    try:
        issued = _dt.datetime.fromisoformat(issued_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return (_utc_now() - issued).days


# ────────────────────────── diagnose ──────────────────────────

def diagnose(cfg: config.Config | None = None) -> list[dict[str, Any]]:
    """Return findings list."""
    if cfg is None:
        cfg = config.load()
    findings: list[dict[str, Any]] = []

    if not caam.caam_present(cfg):
        findings.append({
            "severity": "CRITICAL", "code": "no_caam",
            "message": "caam binary not found on PATH",
            "fix": "go install github.com/Dicklesworthstone/coding_agent_account_manager/cmd/caam@latest",
        })
        return findings

    profiles = caam.profile_summary(cfg)
    profile_count = len(profiles)

    if profile_count == 0:
        findings.append({
            "severity": "HIGH", "code": "no_profiles",
            "message": "no caam profiles configured — system is fully inert",
            "fix": "cmax setup",
        })
    elif profile_count < 2:
        findings.append({
            "severity": "MEDIUM", "code": "single_profile",
            "message": "only 1 profile — rotation has nothing to alternate to",
            "fix": "cmax setup (adds the second profile)",
        })

    healthy = [p for p in profiles if (p.get("health") in ("healthy", "ok"))]
    if profile_count >= 1 and not healthy:
        findings.append({
            "severity": "HIGH", "code": "no_healthy_profiles",
            "message": "all profiles are unhealthy (likely keychain ACL bug after reboot)",
            "fix": "cmax recover (re-/login each profile)",
        })

    warn_d = cfg.storage.token_age_warn_days
    crit_d = cfg.storage.token_age_critical_days
    for p in profiles:
        name = p.get("name") or "?"
        token_present = bool(secrets.get_token(name)) if name != "?" else False
        if not token_present:
            findings.append({
                "severity": "MEDIUM", "code": f"no_token_{name}",
                "message": f"profile {name} has no long-lived token stored",
                "fix": f"cmax rotate {name}",
            })
        else:
            age = token_age_days(name)
            if age is not None and age >= crit_d:
                findings.append({
                    "severity": "HIGH", "code": f"token_expired_{name}",
                    "message": f"token for {name} is {age}d old (>= {crit_d}d, likely expired)",
                    "fix": f"cmax rotate {name}",
                })
            elif age is not None and age >= warn_d:
                findings.append({
                    "severity": "LOW", "code": f"token_aging_{name}",
                    "message": f"token for {name} is {age}d old (>= {warn_d}d, rotate soon)",
                    "fix": f"cmax rotate {name}",
                })
        # profile_stub: caam dir exists but no creds
        cred = caam.profile_creds_path(name, cfg)
        d = caam.profile_dir(name, cfg)
        if d.exists() and not cred.exists():
            findings.append({
                "severity": "MEDIUM", "code": f"profile_stub_{name}",
                "message": f"profile {name} dir exists but credentials missing",
                "fix": "cmax setup (will detect and re-provision)",
            })

    if profile_count >= 2 and not platform.schedule_status("watcher", cfg.meta.repo_owner):
        findings.append({
            "severity": "MEDIUM", "code": "watcher_not_loaded",
            "message": "rotate-watcher schedule is not active",
            "fix": "cmax recover (or `cmax setup` to re-stage)",
        })
    if not platform.schedule_status("watchdog", cfg.meta.repo_owner):
        findings.append({
            "severity": "LOW", "code": "watchdog_not_loaded",
            "message": "daily watchdog schedule is not active",
            "fix": "cmax recover (or `cmax setup` to re-stage)",
        })

    backups = count_backups()
    if backups > 100:
        findings.append({
            "severity": "LOW", "code": "backups_pile",
            "message": f"caam wrote {backups} backups — prune",
            "fix": "cmax recover (prunes >24h)",
        })

    if paths.degraded_flag_path().exists():
        try:
            reason = paths.degraded_flag_path().read_text().strip()
        except OSError:
            reason = "unknown"
        findings.append({
            "severity": "HIGH", "code": "degraded",
            "message": f"degradation flag set: {reason}",
            "fix": "cmax doctor --fix; cmax recover",
        })

    # Schema drift
    if cfg.source_path is not None and cfg.meta.schema_version != config.CURRENT_SCHEMA_VERSION:
        findings.append({
            "severity": "HIGH", "code": "config_schema_version_drift",
            "message": (f"config schema_version={cfg.meta.schema_version}, "
                        f"current={config.CURRENT_SCHEMA_VERSION}"),
            "fix": "cmax migrate",
        })

    # Linux-only: secret-tool absence is a warning when keychain backend is desired
    if not platform.is_macos() and cfg.storage.backend in ("auto", "secret_tool"):
        if not shutil.which("secret-tool"):
            findings.append({
                "severity": "LOW", "code": "secret_tool_missing",
                "message": "secret-tool not on PATH; storage will fall back to env file",
                "fix": "install libsecret-tools (Debian/Ubuntu) or libsecret (Arch/Fedora)",
            })

    return findings


# ────────────────────────── autofix ──────────────────────────

def autofix(findings: list[dict[str, Any]],
            cfg: config.Config | None = None) -> list[str]:
    """Apply non-interactive fixes. Returns log lines."""
    if cfg is None:
        cfg = config.load()
    log: list[str] = []
    codes = {f.get("code") for f in findings}

    if "watcher_not_loaded" in codes:
        # We don't auto-stage here (setup does that). If staged but unloaded,
        # try to load.
        ok, err = platform.schedule_install(
            "watcher",
            ["python3", "-m", "cmaxctl.watcher"],
            every_s=cfg.watcher.interval_s,
            owner=cfg.meta.repo_owner,
        )
        log.append(f"load watcher: {'OK' if ok else f'FAIL ({err})'}")
    if "watchdog_not_loaded" in codes:
        ok, err = platform.schedule_install(
            "watchdog",
            ["python3", "-m", "cmaxctl.watchdog"],
            every_s=86400,  # daily
            owner=cfg.meta.repo_owner,
        )
        log.append(f"load watchdog: {'OK' if ok else f'FAIL ({err})'}")

    if "backups_pile" in codes:
        n = prune_backups(keep_minutes=cfg.watchdog.prune_keep_minutes)
        log.append(f"prune backups: {n} files")

    if "degraded" in codes:
        try:
            paths.degraded_flag_path().unlink(missing_ok=True)
            log.append("cleared degradation flag (will re-set on next failure)")
        except OSError:
            pass

    return log
