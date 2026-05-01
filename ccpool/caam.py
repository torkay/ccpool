"""ccpool/caam.py — caam binary wrapper.

Single contract surface for every caam CLI call ccpool makes. ADR-0006
documents the pinned shape; this module is the only place it's encoded.

All functions tolerate caam being absent (return None / [] / False rather
than raise) so callers can degrade gracefully.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ccpool import config, paths

_EXPORT_RE = re.compile(r'^\s*export\s+([A-Z_][A-Z0-9_]*)=(.*)$')


def caam_bin(cfg: config.Config | None = None) -> str | None:
    """Resolve the caam binary path.

    Priority: cfg.provider.caam_bin → $PATH (via shutil.which) → None.
    """
    if cfg and cfg.provider.caam_bin:
        return cfg.provider.caam_bin
    return shutil.which("caam")


def caam_present(cfg: config.Config | None = None) -> bool:
    return caam_bin(cfg) is not None


def _run(cfg: config.Config | None, args: list[str], timeout: float = 5.0,
         input_text: str | None = None) -> tuple[int, str, str]:
    """Invoke caam <args>. Returns (rc, stdout, stderr); rc=127 if absent."""
    binp = caam_bin(cfg)
    if not binp:
        return 127, "", "caam not on PATH"
    try:
        proc = subprocess.run(
            [binp, *args], capture_output=True, text=True,
            timeout=timeout, input=input_text,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def _strip_quotes(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
        return v[1:-1]
    return v


# ────────────────────────── status ──────────────────────────

def caam_status(cfg: config.Config | None = None) -> dict[str, Any]:
    """Full caam robot status JSON for the configured provider, or {} on failure."""
    provider = (cfg.provider.name if cfg else "claude")
    rc, out, _ = _run(cfg, ["robot", "status", provider])
    if rc != 0:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def caam_env_for(profile: str, cfg: config.Config | None = None) -> dict[str, str] | None:
    """Returns the env dict caam emits for `caam env <provider> <profile>`."""
    provider = (cfg.provider.name if cfg else "claude")
    rc, out, _ = _run(cfg, ["env", provider, profile], timeout=3.0)
    if rc != 0:
        return None
    env: dict[str, str] = {}
    for line in out.splitlines():
        m = _EXPORT_RE.match(line)
        if not m:
            continue
        env[m.group(1)] = _strip_quotes(m.group(2))
    return env or None


def caam_next(cfg: config.Config | None = None, strategy: str = "smart") -> str | None:
    """Tier-2 picker fallback. Returns profile name or None."""
    provider = (cfg.provider.name if cfg else "claude")
    rc, out, _ = _run(cfg, ["robot", "next", provider, "--strategy", strategy])
    if rc != 0:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    p = (data.get("data") or {}).get("profile")
    if isinstance(p, dict):
        return p.get("name")
    if isinstance(p, str):
        return p
    return None


def caam_precheck(cfg: config.Config | None = None,
                  no_fetch: bool = False) -> dict[str, Any] | None:
    provider = (cfg.provider.name if cfg else "claude")
    args = ["robot", "precheck", provider]
    if no_fetch:
        args.append("--no-fetch")
    rc, out, _ = _run(cfg, args, timeout=35.0 if not no_fetch else 5.0)
    if rc != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def caam_activate(profile: str, cfg: config.Config | None = None) -> bool:
    provider = (cfg.provider.name if cfg else "claude")
    rc, out, _ = _run(cfg, ["robot", "act", "activate", provider, profile])
    if rc != 0:
        return False
    try:
        return bool(json.loads(out).get("success"))
    except json.JSONDecodeError:
        return False


# ────────────────────────── profile lifecycle ──────────────────────────

def profile_dir(profile: str, cfg: config.Config | None = None) -> Path:
    provider = (cfg.provider.name if cfg else "claude")
    return paths.caam_profile_dir(provider, profile)


def profile_creds_path(profile: str, cfg: config.Config | None = None) -> Path:
    provider = (cfg.provider.name if cfg else "claude")
    return paths.caam_profile_creds_path(provider, profile)


def profile_ensure(profile: str, description: str = "",
                   cfg: config.Config | None = None) -> tuple[bool, str]:
    """Create the isolated caam profile if absent. Treats 'already exists' as success.

    Returns (ok, error_or_empty).
    """
    if profile_dir(profile, cfg).is_dir():
        return True, ""
    provider = (cfg.provider.name if cfg else "claude")
    desc = description or f"ccpool-managed {provider} profile ({profile})"
    rc, out, err = _run(cfg, ["profile", "add", provider, profile, "-d", desc], timeout=15.0)
    if rc == 0 or profile_dir(profile, cfg).is_dir():
        return True, ""
    combined = (err or out or "").strip()
    if "already exists" in combined.lower():
        return True, ""
    return False, combined or "caam profile add failed"


def profile_purge(profile: str, cfg: config.Config | None = None) -> bool:
    """Remove a half-provisioned profile. Returns True on success.

    Tries `caam profile delete` first; falls back to filesystem rm.
    """
    provider = (cfg.provider.name if cfg else "claude")
    rc, _, _ = _run(cfg, ["profile", "delete", provider, profile, "--force"], timeout=5.0)
    if rc == 0:
        return True
    d = profile_dir(profile, cfg)
    if d.exists():
        try:
            import shutil as _shutil
            _shutil.rmtree(d)
            return True
        except OSError:
            return False
    return True  # already gone


# ────────────────────────── filesystem-first profile enumeration ──────────────────────────

def filesystem_profiles(cfg: config.Config | None = None) -> list[str]:
    """Profile names from the filesystem (caam dev builds emit empty list from
    `robot status` even when profiles exist). Authoritative."""
    provider = (cfg.provider.name if cfg else "claude")
    root = paths.caam_state_dir() / "profiles" / provider
    if not root.exists():
        return []
    out: list[str] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        if paths.caam_profile_creds_path(provider, d.name).exists():
            out.append(d.name)
    return out


def healthy_profiles(cfg: config.Config | None = None) -> list[str]:
    """Filesystem-first list of profiles that have credentials AND are not in
    cooldown according to caam's robot status (when it reports). Used by
    pick.py and watcher.py."""
    fs = filesystem_profiles(cfg)
    if not fs:
        return []
    cooldown: set[str] = set()
    data = caam_status(cfg)
    providers = (data.get("data") or {}).get("providers") or []
    if providers:
        for p in providers[0].get("profiles") or []:
            if not isinstance(p, dict):
                continue
            health = p.get("health")
            status = health.get("status") if isinstance(health, dict) else health
            if status not in (None, "", "healthy", "ok"):
                name = p.get("name")
                if name:
                    cooldown.add(name)
    return [p for p in fs if p not in cooldown]


def profile_summary(cfg: config.Config | None = None) -> list[dict[str, Any]]:
    """Filesystem-first enumeration enriched with robot status fields."""
    provider = (cfg.provider.name if cfg else "claude")
    fs_profiles: dict[str, dict] = {}
    root = paths.caam_state_dir() / "profiles" / provider
    if root.exists():
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            cred = paths.caam_profile_creds_path(provider, d.name)
            fs_profiles[d.name] = {
                "name": d.name,
                "health": "healthy" if cred.exists() else "no-creds",
                "active": False,
            }
    data = caam_status(cfg)
    providers = (data.get("data") or {}).get("providers") or []
    if providers:
        for p in providers[0].get("profiles") or []:
            if not isinstance(p, dict):
                continue
            name = p.get("name")
            if not name:
                continue
            row = fs_profiles.setdefault(name, {"name": name, "health": "unknown", "active": False})
            for k, v in p.items():
                if v is not None:
                    row[k] = v
    return list(fs_profiles.values())
