"""cmaxctl/cli.py — Python entrypoint.

`cmaxctl <subcommand> [args]` — dispatches to module functions.

This is the entrypoint registered in pyproject.toml as `cmaxctl`. The bash
dispatcher at `bin/cmax` handles the *runtime hot path* (`cmax <claude-args>`)
in shell for speed; everything else delegates here.

Subcommands:
    status          — dashboard
    doctor [--fix]  — health check
    pick [--token]  — debug picker
    usage [--json]  — live ground-truth
    inventory       — full state JSON
    statusline      — one-line JSON for prompts
    recover         — reload schedules, prune, clear flags
    logs [-n N]     — tail watcher events
    migrate {detect|plan|apply}  — v0→v1
    install-shell   — write/update managed block
    remove-shell    — strip managed block
    record-token <profile> <account>   — internal: bump age tracker
    version         — print versions

Exit codes:
    0  ok
    1  HIGH/CRITICAL doctor finding (or generic failure)
    2  MEDIUM doctor finding
    64 usage error
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Any

from cmaxctl import (
    _version, blocks, caam, config, doctor, identity, migrate,
    notify, paths, pick, secrets, shell, status, statusline, usage,
)


# ────────────────────────── helpers ──────────────────────────

def _print_findings(findings: list[dict[str, Any]], machine: bool) -> None:
    if machine:
        print(json.dumps({
            "findings": findings,
            "highest_severity": doctor.highest_severity(findings),
        }, indent=2))
        return
    if not findings:
        from cmaxctl.status import GREEN, _c
        print(_c("✓ no findings — cmaxctl is fully green", GREEN))
        return
    by_sev: dict[str, list] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for f in findings:
        by_sev.setdefault(f.get("severity", "LOW"), []).append(f)
    from cmaxctl.status import RED, YELLOW, GREY, DIM, _c
    out: list[str] = []
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if not by_sev.get(sev):
            continue
        c = RED if sev in ("CRITICAL", "HIGH") else YELLOW if sev == "MEDIUM" else GREY
        out.append(_c(f"{sev}", c) + _c(f"  ({len(by_sev[sev])})", DIM))
        for f in by_sev[sev]:
            out.append(f"  • {f.get('message')}")
            out.append(_c(f"    fix: {f.get('fix')}", DIM))
        out.append("")
    print("\n".join(out).rstrip())


def _doctor_exit_code(findings: list[dict[str, Any]]) -> int:
    sev = doctor.highest_severity(findings)
    return {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 2, "LOW": 0, None: 0}[sev]


# ────────────────────────── commands ──────────────────────────

def cmd_status(args: list[str]) -> int:
    cfg = config.load()
    s = status.gather_status(cfg)
    if "--json" in args:
        print(status.render_status_json(s))
    else:
        print(status.render_status_human(s))
    return 0


def cmd_doctor(args: list[str]) -> int:
    cfg = config.load()
    findings = doctor.diagnose(cfg)
    machine = "--json" in args or "--machine" in args
    if "--fix" in args:
        log = doctor.autofix(findings, cfg)
        findings = doctor.diagnose(cfg)
        if not machine:
            from cmaxctl.status import _c, DIM
            for ln in log:
                print(_c(f"  fix: {ln}", DIM))
            print()
    _print_findings(findings, machine)
    return _doctor_exit_code(findings)


def cmd_pick(args: list[str]) -> int:
    cfg = config.load()
    mode = "token" if "--token" in args else "profile"
    e = pick.pick_env_with_token(cfg) if mode == "token" else pick.pick_env(cfg)
    if e is None:
        print(json.dumps({"ok": False, "reason": "no_eligible", "mode": mode}))
        return 1
    redacted = {k: ("<redacted>" if "TOKEN" in k else v) for k, v in e.items()}
    print(json.dumps({"ok": True, "mode": mode, "env": redacted}, indent=2))
    return 0


def cmd_usage(args: list[str]) -> int:
    cfg = config.load()
    profiles_in = caam.healthy_profiles(cfg) or [None]
    snapshots: dict = {}
    profiles_to_fetch = [p for p in profiles_in if p]
    if profiles_to_fetch:
        results = usage.fetch_all(profiles_to_fetch, cfg=cfg)
        for p, u in results.items():
            snapshots[p] = _usage_snapshot(u)
    if None in profiles_in or not profiles_to_fetch:
        u = usage.fetch(None, cfg=cfg)
        snapshots["__default__"] = _usage_snapshot(u)

    if "--json" in args:
        print(json.dumps({"profiles": snapshots}, indent=2, default=str))
        return 0

    # Human render (opus column dropped, dollars formatting)
    from cmaxctl.status import BOLD, DIM, GREEN, YELLOW, RED, _c

    def _fmt_pct(p: float | None) -> str:
        if p is None:
            return "—"
        col = RED if p >= 95 else (YELLOW if p >= 60 else GREEN)
        return _c(f"{p:5.1f}%", col)

    def _resets(iso_str: str | None) -> str:
        if not iso_str:
            return "—"
        from datetime import datetime, timezone
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "—"
        secs = int((dt - datetime.now(timezone.utc)).total_seconds())
        if secs <= 0:
            return "now"
        h, rem = divmod(secs, 3600)
        m, _ = divmod(rem, 60)
        if h >= 24:
            d, hh = divmod(h, 24)
            return f"{d}d{hh}h"
        return f"{h}h{m:02d}m" if h else f"{m}m"

    print(_c("cmaxctl usage (ground truth from /api/oauth/usage)", BOLD))
    print()
    print(_c(f"{'profile':<14} {'5h util':>8} {'5h reset':>10} {'7d util':>8} {'7d reset':>10} {'sonnet':>7}", DIM))
    for key, snap in snapshots.items():
        if not snap.get("ok"):
            print(f"{key:<14} {_c('unreachable', RED)}")
            continue
        print(
            f"{key:<14} "
            f"{_fmt_pct(snap['five_hour_pct']):>8} "
            f"{_resets(snap['five_hour_resets_at']):>10} "
            f"{_fmt_pct(snap['seven_day_pct']):>8} "
            f"{_resets(snap['seven_day_resets_at']):>10} "
            f"{_fmt_pct(snap['seven_day_sonnet_pct']):>7}"
        )

    has_extra = any(s.get("extra_usage_pct") is not None for s in snapshots.values() if s.get("ok"))
    if has_extra:
        print()
        print(_c("PAYG credits", DIM))
        for key, snap in snapshots.items():
            if not snap.get("ok") or snap.get("extra_usage_pct") is None:
                continue
            used = snap.get("extra_usage_used_dollars") or 0.0
            limit = snap.get("extra_usage_limit_dollars") or 0.0
            cur = snap.get("extra_usage_currency") or ""
            print(f"  {key:<12} {_fmt_pct(snap['extra_usage_pct'])}  (${used:,.2f} / ${limit:,.2f} {cur})")

    if paths.saturated_flag_path().exists():
        try:
            detail = json.loads(paths.saturated_flag_path().read_text())
        except (OSError, json.JSONDecodeError):
            detail = {}
        action = detail.get("action") or "unknown"
        print()
        print(_c(f"⚠  saturated: action={action}", YELLOW))
    return 0


def _usage_snapshot(u) -> dict:
    if u is None:
        return {"ok": False}
    return {
        "ok": True,
        "five_hour_pct": u.five_hour.utilization if u.five_hour else None,
        "five_hour_resets_at": u.five_hour.resets_at if u.five_hour else None,
        "seven_day_pct": u.seven_day.utilization if u.seven_day else None,
        "seven_day_resets_at": u.seven_day.resets_at if u.seven_day else None,
        "seven_day_sonnet_pct": u.seven_day_sonnet.utilization if u.seven_day_sonnet else None,
        "extra_usage_pct": u.extra_usage_pct,
        "extra_usage_used_dollars": u.extra_usage_used_dollars,
        "extra_usage_limit_dollars": u.extra_usage_limit_dollars,
        "extra_usage_currency": u.extra_usage_currency,
    }


def cmd_inventory(args: list[str]) -> int:
    """Full state snapshot for setup-time decision making (consumed by bin/cmax)."""
    cfg = config.load()
    inv: dict = {
        "caam_present": caam.caam_present(cfg),
        "claude_present": shutil.which("claude") is not None,
        "schedule_kind": __import__("cmaxctl.platform", fromlist=["schedule_kind"]).schedule_kind(),
        "config_path": str(cfg.source_path) if cfg.source_path else None,
        "profiles": {},
        "tokens": {},
    }
    for p in caam.profile_summary(cfg):
        name = p.get("name") or "?"
        inv["profiles"][name] = {
            "credentials_present": caam.profile_creds_path(name, cfg).exists(),
            "health": (p.get("health", {}).get("status") if isinstance(p.get("health"), dict) else p.get("health")) or "unknown",
        }
    for name in inv["profiles"]:
        tok = secrets.get_token(name)
        slot: dict = {"present": tok is not None}
        if tok:
            slot["looks_valid"] = bool(tok.startswith("sk-ant-oat01-") and len(tok) > 60)
            slot["backend"] = secrets.list_tokens().get(name, "unknown")
        # Probe per-profile usage-scope token
        env = caam.caam_env_for(name, cfg)
        usage_response = None
        if env and env.get("CLAUDE_CONFIG_DIR"):
            from pathlib import Path
            cred = Path(env["CLAUDE_CONFIG_DIR"]).expanduser() / ".credentials.json"
            if cred.exists():
                try:
                    d = json.loads(cred.read_text())
                    inner = d.get("claudeAiOauth") or d
                    creds_token = inner.get("accessToken") or inner.get("access_token")
                    if creds_token:
                        usage_response = identity.validate_oauth_token(creds_token)
                except (OSError, json.JSONDecodeError):
                    pass
        slot["usage_scope_works"] = usage_response is not None
        slot["fingerprint"] = identity.token_fingerprint(usage_response)
        inv["tokens"][name] = slot
    print(json.dumps(inv, indent=2, default=str))
    return 0


def cmd_statusline(args: list[str]) -> int:
    cfg = config.load()
    s = statusline.snapshot(cfg)
    if "--short" in args:
        print(statusline.render_short(s))
    else:
        print(json.dumps(s))
    return 0


def cmd_recover(args: list[str]) -> int:
    cfg = config.load()
    actions: list[str] = []
    n = doctor.prune_backups(keep_minutes=cfg.watchdog.prune_keep_minutes)
    actions.append(f"pruned {n} stale backups")
    if paths.degraded_flag_path().exists():
        try:
            paths.degraded_flag_path().unlink()
            actions.append("cleared degraded flag")
        except OSError:
            pass
    findings = doctor.diagnose(cfg)
    log = doctor.autofix(findings, cfg)
    actions.extend(log)
    for a in actions:
        print(a)
    print()
    return cmd_doctor(args)


def cmd_logs(args: list[str]) -> int:
    n = 30
    if "-n" in args:
        try:
            n = int(args[args.index("-n") + 1])
        except (IndexError, ValueError):
            pass
    p = paths.watcher_log_path()
    if not p.exists():
        return 0
    try:
        lines = p.read_text().splitlines()[-n:]
    except OSError:
        lines = []
    for ln in lines:
        try:
            print(json.dumps(json.loads(ln)))
        except json.JSONDecodeError:
            continue
    return 0


def cmd_migrate(args: list[str]) -> int:
    saved = sys.argv
    sys.argv = ["cmaxctl-migrate", *args]
    try:
        return migrate.main()
    finally:
        sys.argv = saved


def cmd_install_shell(args: list[str]) -> int:
    cfg = config.load()
    log = shell.install(cfg)
    for path, action in log:
        print(f"{action}: {path}")
    return 0


def cmd_remove_shell(args: list[str]) -> int:
    cfg = config.load()
    paths_modified = shell.remove(cfg)
    for p in paths_modified:
        print(f"stripped: {p}")
    return 0


def cmd_record_token(args: list[str]) -> int:
    if len(args) < 2:
        print("usage: cmaxctl record-token <profile> <account>", file=sys.stderr)
        return 64
    profile, account = args[0], args[1]
    import datetime as _dt
    p = paths.tokens_json_path()
    data: dict = {}
    if p.exists():
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    data[profile] = {
        "issued_at": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "account": account,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(p)
    return 0


def cmd_version(args: list[str]) -> int:
    print(f"cmaxctl: {_version.__version__}")
    cb = caam.caam_bin()
    if cb:
        # caam uses `caam version` as a subcommand (not `--version` flag)
        rc = subprocess.run([cb, "version"], capture_output=True, text=True, timeout=3)
        v = (rc.stdout or rc.stderr).strip().splitlines()[0] if (rc.stdout or rc.stderr) else "unknown"
        print(f"caam:    {v}")
    else:
        print("caam:    NOT INSTALLED")
    cl = shutil.which("claude")
    if cl:
        rc = subprocess.run([cl, "--version"], capture_output=True, text=True, timeout=3)
        v = rc.stdout.strip() or "unknown"
        print(f"claude:  {v}")
    else:
        print("claude:  NOT INSTALLED")
    return 0


# ────────────────────────── dispatch ──────────────────────────

COMMANDS = {
    "status": cmd_status,
    "doctor": cmd_doctor,
    "pick": cmd_pick,
    "usage": cmd_usage,
    "inventory": cmd_inventory,
    "statusline": cmd_statusline,
    "recover": cmd_recover,
    "logs": cmd_logs,
    "migrate": cmd_migrate,
    "install-shell": cmd_install_shell,
    "remove-shell": cmd_remove_shell,
    "record-token": cmd_record_token,
    "version": cmd_version,
}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: cmaxctl <subcommand> [args]", file=sys.stderr)
        print("subcommands: " + ", ".join(sorted(COMMANDS.keys())), file=sys.stderr)
        return 64
    sub = sys.argv[1]
    rest = sys.argv[2:]
    fn = COMMANDS.get(sub)
    if not fn:
        print(f"unknown subcommand: {sub}", file=sys.stderr)
        print("subcommands: " + ", ".join(sorted(COMMANDS.keys())), file=sys.stderr)
        return 64
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
