"""ccpool/platform.py — OS detection + scheduler abstraction.

Exposes:
    is_macos() / is_linux() / is_freebsd()
    open_url(url)                       # opens in default browser
    schedule_kind()                     # "launchd" | "systemd_user" | "cron" | "none"
    schedule_install(kind, argv, every) # install a recurring tick job
    schedule_remove(kind)               # remove the job
    schedule_status(kind)               # currently loaded?

`kind` is one of "watcher", "watchdog" (matches paths.schedule_label).
`every` is interval in seconds (watcher) or seconds-of-day for watchdog.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from ccpool import paths

# ────────────────────────── OS detection ──────────────────────────

def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def is_freebsd() -> bool:
    return sys.platform.startswith("freebsd")


def is_posix() -> bool:
    return os.name == "posix"


# ────────────────────────── browser ──────────────────────────

def open_url(url: str) -> bool:
    """Best-effort open in default browser. Returns True if the command
    was issued; never raises (caller falls through to printing the URL)."""
    if is_macos():
        cmd = ["open", url]
    elif is_linux() or is_freebsd():
        if shutil.which("xdg-open"):
            cmd = ["xdg-open", url]
        elif shutil.which("gnome-open"):
            cmd = ["gnome-open", url]
        else:
            return False
    else:
        return False
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, OSError):
        return False


# ────────────────────────── scheduler kind ──────────────────────────

def schedule_kind() -> str:
    """Return the best-available scheduling primitive on this host."""
    if is_macos():
        return "launchd"
    if is_linux() or is_freebsd():
        # Prefer systemd-user when available (XDG_RUNTIME_DIR set + systemctl --user works)
        if _systemd_user_available():
            return "systemd_user"
        if shutil.which("crontab"):
            return "cron"
        return "none"
    return "none"


def _systemd_user_available() -> bool:
    if not shutil.which("systemctl"):
        return False
    try:
        rc = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True, text=True, timeout=3,
        )
        # Even "degraded" is fine for our purposes; we just need user-bus.
        return rc.returncode in (0, 1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ────────────────────────── launchd (macOS) ──────────────────────────

def _launchd_install(label: str, plist_path: Path, argv: list[str], every_s: int) -> tuple[bool, str]:
    plist_xml = _render_launchd_plist(label, argv, every_s)
    paths.ensure_config_parent(plist_path)
    plist_path.write_text(plist_xml)
    rc = subprocess.run(["launchctl", "load", str(plist_path)],
                        capture_output=True, text=True, timeout=10)
    if rc.returncode != 0:
        return False, rc.stderr.strip() or "launchctl load failed"
    return True, ""


def _launchd_remove(label: str, plist_path: Path) -> tuple[bool, str]:
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)],
                       capture_output=True, text=True, timeout=5)
        try:
            plist_path.unlink()
        except OSError as exc:
            return False, str(exc)
    return True, ""


def _launchd_loaded(label: str) -> bool:
    rc = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
    return rc.returncode == 0 and label in rc.stdout


def _render_launchd_plist(label: str, argv: list[str], every_s: int) -> str:
    args_xml = "\n        ".join(f"<string>{_escape_xml(a)}</string>" for a in argv)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_escape_xml(label)}</string>
    <key>ProgramArguments</key>
    <array>
        {args_xml}
    </array>
    <key>StartInterval</key>
    <integer>{int(every_s)}</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>/dev/null</string>
</dict>
</plist>
"""


def _escape_xml(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


# ────────────────────────── systemd-user (Linux) ──────────────────────────

def _systemd_install(unit_name: str, service_path: Path, timer_path: Path,
                     argv: list[str], every_s: int) -> tuple[bool, str]:
    paths.ensure_config_parent(service_path)
    paths.ensure_config_parent(timer_path)
    exec_start = " ".join(_systemd_quote(a) for a in argv)
    service_path.write_text(f"""[Unit]
Description=ccpool {unit_name} tick
After=network-online.target

[Service]
Type=oneshot
ExecStart={exec_start}
""")
    timer_path.write_text(f"""[Unit]
Description=ccpool {unit_name} timer

[Timer]
OnBootSec=60s
OnUnitInactiveSec={int(every_s)}s
Unit={service_path.name}

[Install]
WantedBy=timers.target
""")
    subprocess.run(["systemctl", "--user", "daemon-reload"],
                   capture_output=True, text=True, timeout=5)
    rc = subprocess.run(
        ["systemctl", "--user", "enable", "--now", timer_path.name],
        capture_output=True, text=True, timeout=10,
    )
    if rc.returncode != 0:
        return False, rc.stderr.strip() or "systemctl enable failed"
    return True, ""


def _systemd_remove(service_path: Path, timer_path: Path) -> tuple[bool, str]:
    if timer_path.exists():
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", timer_path.name],
            capture_output=True, text=True, timeout=5,
        )
        try:
            timer_path.unlink()
        except OSError:
            pass
    if service_path.exists():
        try:
            service_path.unlink()
        except OSError:
            pass
    subprocess.run(["systemctl", "--user", "daemon-reload"],
                   capture_output=True, text=True, timeout=5)
    return True, ""


def _systemd_loaded(timer_unit: str) -> bool:
    rc = subprocess.run(
        ["systemctl", "--user", "is-active", timer_unit],
        capture_output=True, text=True, timeout=3,
    )
    return rc.returncode == 0


def _systemd_quote(s: str) -> str:
    if not s or any(c in s for c in (" ", "\t", "$", '"')):
        return '"' + s.replace('"', '\\"') + '"'
    return s


# ────────────────────────── cron fallback ──────────────────────────

def _cron_install(label: str, argv: list[str], every_s: int) -> tuple[bool, str]:
    """Ultra-minimal: append a comment-marked line to the user's crontab.

    every_s rounds up to the nearest minute. Watchdog at >=86400 (1 day)
    becomes a daily 04:30 schedule.
    """
    rc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=3)
    existing = rc.stdout if rc.returncode == 0 else ""
    marker = f"# ccpool:{label}"
    lines = [ln for ln in existing.splitlines() if marker not in ln]
    cmd = " ".join(_systemd_quote(a) for a in argv)
    if every_s >= 86400:
        schedule = "30 4 * * *"
    else:
        minutes = max(1, every_s // 60)
        schedule = f"*/{minutes} * * * *"
    lines.append(f"{schedule} {cmd}  {marker}")
    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab,
                          capture_output=True, text=True, timeout=5)
    if proc.returncode != 0:
        return False, proc.stderr.strip() or "crontab write failed"
    return True, ""


def _cron_remove(label: str) -> tuple[bool, str]:
    rc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=3)
    existing = rc.stdout if rc.returncode == 0 else ""
    marker = f"# ccpool:{label}"
    lines = [ln for ln in existing.splitlines() if marker not in ln]
    new_crontab = "\n".join(lines) + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab,
                          capture_output=True, text=True, timeout=5)
    return proc.returncode == 0, proc.stderr.strip()


def _cron_loaded(label: str) -> bool:
    rc = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=3)
    if rc.returncode != 0:
        return False
    return f"# ccpool:{label}" in rc.stdout


# ────────────────────────── public API ──────────────────────────

def schedule_install(kind: str, argv: list[str], every_s: int,
                     owner: str | None = None) -> tuple[bool, str]:
    """Install a recurring tick. Returns (ok, error_or_empty)."""
    primitive = schedule_kind()
    if primitive == "launchd":
        label = paths.schedule_label(owner, kind)
        return _launchd_install(label, paths.macos_plist_path(owner, kind), argv, every_s)
    if primitive == "systemd_user":
        return _systemd_install(
            kind,
            paths.systemd_service_path(kind),
            paths.systemd_timer_path(kind),
            argv,
            every_s,
        )
    if primitive == "cron":
        return _cron_install(kind, argv, every_s)
    return False, "no scheduling primitive available on this host"


def schedule_remove(kind: str, owner: str | None = None) -> tuple[bool, str]:
    primitive = schedule_kind()
    if primitive == "launchd":
        label = paths.schedule_label(owner, kind)
        return _launchd_remove(label, paths.macos_plist_path(owner, kind))
    if primitive == "systemd_user":
        return _systemd_remove(paths.systemd_service_path(kind), paths.systemd_timer_path(kind))
    if primitive == "cron":
        return _cron_remove(kind)
    return True, ""


def schedule_status(kind: str, owner: str | None = None) -> bool:
    primitive = schedule_kind()
    if primitive == "launchd":
        return _launchd_loaded(paths.schedule_label(owner, kind))
    if primitive == "systemd_user":
        return _systemd_loaded(paths.systemd_timer_path(kind).name)
    if primitive == "cron":
        return _cron_loaded(kind)
    return False
