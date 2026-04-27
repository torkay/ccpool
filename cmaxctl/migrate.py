"""cmaxctl/migrate.py — v0 (personal `cmax` substrate) → v1 (cmaxctl) migrator.

Detects a personal-substrate install (operator's tor1/tor2 + launchd plists with
`com.<owner>.agent.*` labels + zshrc managed block) and migrates state to the
public layout: cmaxctl config.toml + new label scheme + cmaxctl- keychain prefix.

Profiles, tokens, and accounts are preserved. The personal `~/Agent/.agent/tools/`
substrate stays untouched (operator can archive when ready).

Stdlib only.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cmaxctl import caam, config, paths, secrets, shell


@dataclass
class V0Detection:
    detected: bool
    signals: list[str]
    profiles: list[str]
    legacy_plists: list[Path]
    legacy_zshrc_blocks: list[Path]


# Personal-substrate label pattern: `com.<owner>.agent.{caam-rotate-watcher,cmax-watchdog}`
LEGACY_PLIST_RE = re.compile(r"^com\.[^.]+\.agent\.(caam-rotate-watcher|cmax-watchdog)\.plist$")


def detect_v0() -> V0Detection:
    """Return a snapshot of v0 signals on this machine."""
    signals: list[str] = []
    profiles: list[str] = []
    legacy_plists: list[Path] = []
    legacy_zshrc_blocks: list[Path] = []

    # Signal 1: caam profiles named tor1/tor2
    fs = caam.filesystem_profiles()
    if any(p in fs for p in ("tor1", "tor2")):
        signals.append("caam profiles tor1/tor2 present")
        profiles.extend([p for p in fs if p in ("tor1", "tor2")])

    # Signal 2: legacy launchd plists
    launchagent_dir = paths.macos_launchagent_dir()
    if launchagent_dir.exists():
        for p in launchagent_dir.iterdir():
            if LEGACY_PLIST_RE.match(p.name):
                legacy_plists.append(p)
        if legacy_plists:
            signals.append(f"{len(legacy_plists)} legacy launchd plist(s) present")

    # Signal 3: legacy zshrc managed block
    for rc in paths.candidate_shell_rc_files():
        if rc.exists() and rc.suffix != ".fish":
            try:
                if "# >>> cmax (Claude Max rotation)" in rc.read_text():
                    legacy_zshrc_blocks.append(rc)
            except OSError:
                pass
    if legacy_zshrc_blocks:
        signals.append(f"legacy zshrc managed block in {len(legacy_zshrc_blocks)} file(s)")

    # Signal 4: legacy tokens.json (age tracker) at the operator's old location
    legacy_tokens_json = Path.home() / ".local" / "share" / "caam" / "tokens.json"
    if legacy_tokens_json.exists():
        signals.append("legacy tokens.json at ~/.local/share/caam/tokens.json")

    # Signal 5: legacy keychain entries (caam-claude-token-*)
    legacy_kc = []
    if sys.platform == "darwin":
        for p in profiles:
            try:
                proc = subprocess.run(
                    ["security", "find-generic-password",
                     "-s", f"{paths.LEGACY_SERVICE_PREFIX}{p}", "-a", "torrinkay"],
                    capture_output=True, text=True, timeout=2,
                )
                if proc.returncode == 0:
                    legacy_kc.append(p)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    if legacy_kc:
        signals.append(f"legacy keychain entries for {legacy_kc}")

    return V0Detection(
        detected=len(signals) >= 2,
        signals=signals,
        profiles=profiles,
        legacy_plists=legacy_plists,
        legacy_zshrc_blocks=legacy_zshrc_blocks,
    )


def synthesize_config_from_v0(d: V0Detection,
                              repo_owner: str = "") -> config.Config:
    """Build a v1 config.toml from observed v0 state."""
    cfg = config.Config()
    cfg.meta.repo_owner = repo_owner
    # Profile names + emails: read from old tokens.json if present (it stored
    # `account` per profile); fall back to placeholders the operator must edit.
    legacy_tokens = Path.home() / ".local" / "share" / "caam" / "tokens.json"
    accounts: dict[str, str] = {}
    if legacy_tokens.exists():
        try:
            data = json.loads(legacy_tokens.read_text())
            for k, v in data.items():
                if isinstance(v, dict) and v.get("account"):
                    accounts[k] = v["account"]
        except (json.JSONDecodeError, OSError):
            pass
    for name in d.profiles:
        cfg.profiles.append(config.Profile(
            name=name,
            email=accounts.get(name, ""),
            description=f"migrated from v0 personal substrate",
        ))
    return cfg


def migrate_keychain_tokens(profiles: list[str]) -> dict[str, str]:
    """Copy tokens from `caam-claude-token-<p>` to `cmaxctl-token-<p>`.

    Returns {profile: action} where action ∈ {"copied", "no-legacy", "failed"}.
    Does NOT delete the legacy entries (operator can clean up via `cmax doctor`).
    """
    out: dict[str, str] = {}
    if sys.platform != "darwin":
        return {p: "skipped-non-macos" for p in profiles}
    for p in profiles:
        try:
            proc = subprocess.run(
                ["security", "find-generic-password",
                 "-s", f"{paths.LEGACY_SERVICE_PREFIX}{p}", "-w"],
                capture_output=True, text=True, timeout=3,
            )
            if proc.returncode != 0:
                out[p] = "no-legacy"
                continue
            tok = proc.stdout.strip()
            if not tok:
                out[p] = "no-legacy"
                continue
        except (FileNotFoundError, subprocess.TimeoutExpired):
            out[p] = "failed"
            continue
        backend, err = secrets.set_token(p, tok)
        out[p] = "copied" if not err.startswith("native backend failed AND") else "failed"
    return out


@dataclass
class MigrationPlan:
    write_config_to: Path
    write_config_text: str
    move_keychain_for: list[str]
    remove_legacy_plists: list[Path]
    rewrite_shell_rc: list[Path]


def plan(d: V0Detection, repo_owner: str = "") -> MigrationPlan:
    """Compute what migration would do without performing it."""
    cfg = synthesize_config_from_v0(d, repo_owner=repo_owner)
    config_path = paths.default_config_path()
    return MigrationPlan(
        write_config_to=config_path,
        write_config_text=config.render_toml(cfg),
        move_keychain_for=d.profiles,
        remove_legacy_plists=d.legacy_plists,
        rewrite_shell_rc=d.legacy_zshrc_blocks,
    )


def apply(plan_obj: MigrationPlan,
          d: V0Detection,
          repo_owner: str = "") -> dict:
    """Execute the migration. Returns a log dict."""
    log: dict = {"steps": [], "errors": []}

    cfg = synthesize_config_from_v0(d, repo_owner=repo_owner)
    written = config.write(cfg)
    log["steps"].append(f"wrote config to {written}")

    kc = migrate_keychain_tokens(plan_obj.move_keychain_for)
    log["steps"].append({"keychain_migration": kc})

    for plist in plan_obj.remove_legacy_plists:
        try:
            subprocess.run(["launchctl", "unload", str(plist)],
                           capture_output=True, text=True, timeout=5)
            plist.unlink()
            log["steps"].append(f"removed legacy plist {plist.name}")
        except OSError as exc:
            log["errors"].append(f"plist remove {plist.name}: {exc}")

    if plan_obj.rewrite_shell_rc:
        # Strip legacy + install new
        installed = shell.install(cfg)
        log["steps"].append({"shell_rc": [{str(p): a} for p, a in installed]})

    return log


# ────────────────────────── CLI ──────────────────────────

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m cmaxctl.migrate {detect | plan | apply [--owner=NAME]}",
              file=sys.stderr)
        return 64
    cmd = sys.argv[1]
    args = sys.argv[2:]

    owner = ""
    for a in args:
        if a.startswith("--owner="):
            owner = a.split("=", 1)[1]

    if cmd == "detect":
        d = detect_v0()
        print(json.dumps({
            "detected": d.detected,
            "signals": d.signals,
            "profiles": d.profiles,
            "legacy_plists": [str(p) for p in d.legacy_plists],
            "legacy_zshrc_blocks": [str(p) for p in d.legacy_zshrc_blocks],
        }, indent=2))
        return 0 if d.detected else 1
    if cmd == "plan":
        d = detect_v0()
        if not d.detected:
            print(json.dumps({"detected": False}))
            return 1
        p = plan(d, repo_owner=owner)
        print(json.dumps({
            "write_config_to": str(p.write_config_to),
            "config_preview": p.write_config_text,
            "move_keychain_for": p.move_keychain_for,
            "remove_legacy_plists": [str(x) for x in p.remove_legacy_plists],
            "rewrite_shell_rc": [str(x) for x in p.rewrite_shell_rc],
        }, indent=2))
        return 0
    if cmd == "apply":
        d = detect_v0()
        if not d.detected:
            print(json.dumps({"detected": False}))
            return 1
        p = plan(d, repo_owner=owner)
        result = apply(p, d, repo_owner=owner)
        print(json.dumps(result, indent=2, default=str))
        return 0
    print(f"unknown subcommand: {cmd}", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
