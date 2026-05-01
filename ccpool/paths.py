"""ccpool/paths.py — XDG / macOS path resolution.

Single source of truth for every filesystem location ccpool reads or writes.
No personal identifiers; everything derives from $HOME, XDG_*, or sys.platform.

Resolution order for *config*:
    1. $CCPOOL_CONFIG (explicit override; rarely set)
    2. $XDG_CONFIG_HOME/ccpool/config.toml
    3. ~/Library/Application Support/ccpool/config.toml (macOS only)
    4. ~/.config/ccpool/config.toml

Resolution order for *state*:
    1. $XDG_DATA_HOME/ccpool/
    2. ~/.local/share/ccpool/

Resolution order for *cache*:
    1. $XDG_CACHE_HOME/ccpool/
    2. ~/Library/Caches/ccpool/ (macOS) or ~/.cache/ccpool/ (Linux)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "ccpool"

# Keychain service prefix for long-lived OAuth tokens.
SERVICE_PREFIX = "ccpool-token-"
# Legacy prefix used by the personal substrate; migrate.py rewrites this.
LEGACY_SERVICE_PREFIX = "caam-claude-token-"

# launchd plist label / systemd unit prefix is computed from `cfg.repo_owner`
# (or "local" when unset). See `schedule_label()`.
DEFAULT_OWNER = "local"


# ────────────────────────── helpers ──────────────────────────

def _is_macos() -> bool:
    return sys.platform == "darwin"


def _xdg(env_var: str, default: Path) -> Path:
    raw = os.environ.get(env_var, "").strip()
    if raw:
        return Path(raw).expanduser()
    return default


def home() -> Path:
    return Path.home()


# ────────────────────────── config ──────────────────────────

def explicit_config_override() -> Path | None:
    raw = os.environ.get("CCPOOL_CONFIG", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def xdg_config_path() -> Path:
    return _xdg("XDG_CONFIG_HOME", home() / ".config") / APP_NAME / "config.toml"


def macos_app_support_config_path() -> Path:
    return home() / "Library" / "Application Support" / APP_NAME / "config.toml"


def candidate_config_paths() -> list[Path]:
    """Ordered list of paths to try for config discovery."""
    paths: list[Path] = []
    override = explicit_config_override()
    if override is not None:
        paths.append(override)
    paths.append(xdg_config_path())
    if _is_macos():
        paths.append(macos_app_support_config_path())
    paths.append(home() / ".config" / APP_NAME / "config.toml")
    # Dev-mode (in-repo) fallback
    in_repo = Path.cwd() / "ccpool.toml"
    paths.append(in_repo)
    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        s = str(p.resolve()) if p.is_absolute() else str(p)
        if s in seen:
            continue
        seen.add(s)
        out.append(p)
    return out


def default_config_path() -> Path:
    """Where `ccpool setup` writes the config on first run.

    macOS prefers `~/Library/Application Support/ccpool/`; Linux uses XDG.
    The override and dev-mode locations are NOT chosen as defaults.
    """
    if _is_macos():
        return macos_app_support_config_path()
    return xdg_config_path()


# ────────────────────────── state ──────────────────────────

def state_dir() -> Path:
    return _xdg("XDG_DATA_HOME", home() / ".local" / "share") / APP_NAME


def state_file(name: str) -> Path:
    return state_dir() / name


def tokens_env_path() -> Path:
    return state_file("tokens.env")


def tokens_json_path() -> Path:
    return state_file("tokens.json")


def usage_cache_path() -> Path:
    return state_file("usage_cache.json")


def watcher_log_path() -> Path:
    return state_file("watcher.ndjson")


def watcher_counter_path() -> Path:
    return state_file("watcher.counter")


def watcher_last_rotate_path() -> Path:
    return state_file("watcher.last_rotate")


def degraded_flag_path() -> Path:
    return state_file("degraded.flag")


def saturated_flag_path() -> Path:
    return state_file("saturated.flag")


def disabled_flag_path() -> Path:
    return state_file("disabled")


# ────────────────────────── cache ──────────────────────────

def cache_dir() -> Path:
    if _is_macos():
        default = home() / "Library" / "Caches"
    else:
        default = home() / ".cache"
    return _xdg("XDG_CACHE_HOME", default) / APP_NAME


# ────────────────────────── claude / caam ──────────────────────────

def claude_projects_dir() -> Path:
    """Where Claude Code writes JSONL transcripts.

    Honours `XDG_CONFIG_HOME/claude-code/projects` first (some installs put it
    under XDG), then falls back to `~/.claude/projects` (the default).
    """
    xdg_candidate = _xdg("XDG_CONFIG_HOME", home() / ".config") / "claude-code" / "projects"
    if xdg_candidate.exists():
        return xdg_candidate
    return home() / ".claude" / "projects"


def caam_state_dir() -> Path:
    """caam owns this; we only read from it."""
    return home() / ".local" / "share" / "caam"


def caam_profile_dir(provider: str, profile: str) -> Path:
    return caam_state_dir() / "profiles" / provider / profile


def caam_profile_creds_path(provider: str, profile: str) -> Path:
    """Per-profile `.credentials.json` (caam isolates this in xdg_config)."""
    return caam_profile_dir(provider, profile) / "xdg_config" / "claude-code" / ".credentials.json"


# ────────────────────────── schedules ──────────────────────────

def macos_launchagent_dir() -> Path:
    return home() / "Library" / "LaunchAgents"


def systemd_user_unit_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", home() / ".config") / "systemd" / "user"


def schedule_label(owner: str | None, kind: str) -> str:
    """Compute the launchd plist / systemd unit label.

    `owner` is from cfg.meta.repo_owner; absent → DEFAULT_OWNER ("local").
    `kind` is one of "watcher", "watchdog".
    """
    safe_owner = (owner or DEFAULT_OWNER).strip().lower() or DEFAULT_OWNER
    safe_kind = kind.strip().lower()
    return f"io.github.{safe_owner}.{APP_NAME}.{safe_kind}"


def macos_plist_path(owner: str | None, kind: str) -> Path:
    return macos_launchagent_dir() / f"{schedule_label(owner, kind)}.plist"


def systemd_service_path(kind: str) -> Path:
    return systemd_user_unit_dir() / f"{APP_NAME}-{kind}.service"


def systemd_timer_path(kind: str) -> Path:
    return systemd_user_unit_dir() / f"{APP_NAME}-{kind}.timer"


# ────────────────────────── shell rc ──────────────────────────

def candidate_shell_rc_files() -> list[Path]:
    """Files we may write the managed block to. shell.py picks which exist."""
    return [
        home() / ".zshrc",
        home() / ".bashrc",
        home() / ".bash_profile",
        _xdg("XDG_CONFIG_HOME", home() / ".config") / "fish" / "conf.d" / f"{APP_NAME}.fish",
    ]


# ────────────────────────── ensure ──────────────────────────

def ensure_state_dir() -> Path:
    """Create state_dir if needed, with a sensible umask."""
    p = state_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_cache_dir() -> Path:
    p = cache_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_config_parent(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
