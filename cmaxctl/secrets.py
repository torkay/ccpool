"""cmaxctl/secrets.py — token storage with graceful fallback.

Backends in priority order on read (env wins so a deliberate fallback overrides
a stale keychain entry); reverse on write (keychain first, fall through to env):

    1. macOS Keychain (`security` CLI) — when available
    2. Linux libsecret / GNOME-Keyring (`secret-tool` CLI) — when available
    3. Plaintext env file at $XDG_DATA_HOME/cmaxctl/tokens.env (mode 0600) — fallback

Service prefix: `cmaxctl-token-<profile>`. Migration from the legacy
`caam-claude-token-<profile>` prefix is handled in `migrate.py`.

Operator-side override: `CMAXCTL_FORCE_ENV_STORAGE=1` (or the legacy
`CAAM_FORCE_ENV_STORAGE=1` for compat) forces the env backend.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

from cmaxctl import paths

_VALID_PROFILE = re.compile(r"^[a-zA-Z0-9._-]+$")
_ENV_KEY_PREFIX = "CMAXCTL_TOKEN_"
_LEGACY_ENV_KEY_PREFIX = "CAAM_TOKEN_"


# ────────────────────────── helpers ──────────────────────────

def _check_profile(profile: str) -> None:
    if not _VALID_PROFILE.match(profile):
        raise ValueError(f"invalid profile name: {profile!r}")


def force_env() -> bool:
    return (os.environ.get("CMAXCTL_FORCE_ENV_STORAGE") == "1"
            or os.environ.get("CAAM_FORCE_ENV_STORAGE") == "1")


def env_file_path() -> Path:
    return paths.tokens_env_path()


def _ensure_env_file_mode() -> None:
    p = env_file_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.touch()
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _account_user() -> str:
    """Account label for keychain entries. Empty string is invalid; raise.

    No fallback to a hardcoded username — that would be a bug-by-default.
    """
    user = os.environ.get("USER", "").strip()
    if not user:
        raise RuntimeError("$USER not set; cannot determine keychain account label")
    return user


# ────────────────────────── env-file backend ──────────────────────────

def _read_env_file() -> dict[str, str]:
    """Returns {profile: token} after stripping the wire prefix.

    Tolerates BOTH the new (`CMAXCTL_TOKEN_`) and legacy (`CAAM_TOKEN_`)
    prefixes so an in-place migration doesn't lose data."""
    p = env_file_path()
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    try:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            if v.startswith("'") and v.endswith("'"):
                v = v[1:-1]
            elif v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            if k.startswith(_ENV_KEY_PREFIX):
                profile = k[len(_ENV_KEY_PREFIX):]
            elif k.startswith(_LEGACY_ENV_KEY_PREFIX):
                profile = k[len(_LEGACY_ENV_KEY_PREFIX):]
            else:
                continue
            if profile:
                out[profile] = v
    except OSError:
        return {}
    return out


def _write_env_file(values: dict[str, str]) -> bool:
    _ensure_env_file_mode()
    p = env_file_path()
    lines = [f"# cmaxctl token store. mode 600. one {_ENV_KEY_PREFIX}<profile>=<value> per line."]
    for k in sorted(values):
        lines.append(f"{_ENV_KEY_PREFIX}{k}={values[k]}")
    try:
        p.write_text("\n".join(lines) + "\n")
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return True
    except OSError:
        return False


# ────────────────────────── macOS keychain backend ──────────────────────────

def _macos_keychain_get(profile: str) -> str | None:
    _check_profile(profile)
    try:
        proc = subprocess.run(
            ["security", "find-generic-password",
             "-s", f"{paths.SERVICE_PREFIX}{profile}", "-w"],
            capture_output=True, text=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    tok = proc.stdout.strip()
    return tok or None


def _macos_keychain_set(profile: str, token: str, account: str | None = None) -> tuple[bool, str]:
    _check_profile(profile)
    if not token:
        return False, "empty token"
    acct = account or _account_user()
    keychain = str(Path.home() / "Library/Keychains/login.keychain-db")
    cmd = ["security", "add-generic-password", "-U",
           "-s", f"{paths.SERVICE_PREFIX}{profile}",
           "-a", acct,
           "-j", f"cmaxctl OAuth token for profile {profile}",
           "-w", token]
    try:
        # First attempt: explicit -k to defeat the "no keychain to store"
        # error path documented in ADR-0005.
        proc = subprocess.run([*cmd, keychain],
                              capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return True, ""
        err = (proc.stderr or proc.stdout or "").strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        err = str(exc)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return True, ""
        err2 = (proc.stderr or proc.stdout or "").strip()
        return False, err2 or err
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"{err}; retry: {exc}"


def _macos_keychain_delete(profile: str) -> bool:
    _check_profile(profile)
    try:
        proc = subprocess.run(
            ["security", "delete-generic-password",
             "-s", f"{paths.SERVICE_PREFIX}{profile}"],
            capture_output=True, text=True, timeout=3,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ────────────────────────── Linux secret-tool backend ──────────────────────────

def _secret_tool_available() -> bool:
    return _which("secret-tool") is not None


def _secret_tool_get(profile: str) -> str | None:
    _check_profile(profile)
    try:
        proc = subprocess.run(
            ["secret-tool", "lookup", "service", paths.APP_NAME, "profile", profile],
            capture_output=True, text=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    tok = proc.stdout.strip()
    return tok or None


def _secret_tool_set(profile: str, token: str, account: str | None = None) -> tuple[bool, str]:
    _check_profile(profile)
    if not token:
        return False, "empty token"
    label = f"cmaxctl OAuth token for profile {profile}"
    cmd = ["secret-tool", "store", "--label", label,
           "service", paths.APP_NAME,
           "profile", profile]
    try:
        # secret-tool reads the secret from stdin
        proc = subprocess.run(cmd, input=token, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return True, ""
        err = (proc.stderr or proc.stdout or "").strip()
        return False, err or "secret-tool store failed"
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


def _secret_tool_delete(profile: str) -> bool:
    _check_profile(profile)
    try:
        proc = subprocess.run(
            ["secret-tool", "clear", "service", paths.APP_NAME, "profile", profile],
            capture_output=True, text=True, timeout=3,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _which(cmd: str) -> str | None:
    import shutil as _shutil
    return _shutil.which(cmd)


# ────────────────────────── backend dispatch ──────────────────────────

def _is_macos() -> bool:
    return sys.platform == "darwin"


def _native_keychain_get(profile: str) -> str | None:
    if _is_macos():
        return _macos_keychain_get(profile)
    if _secret_tool_available():
        return _secret_tool_get(profile)
    return None


def _native_keychain_set(profile: str, token: str, account: str | None) -> tuple[bool, str]:
    if _is_macos():
        return _macos_keychain_set(profile, token, account)
    if _secret_tool_available():
        return _secret_tool_set(profile, token, account)
    return False, "no native secret backend"


def _native_keychain_delete(profile: str) -> bool:
    if _is_macos():
        return _macos_keychain_delete(profile)
    if _secret_tool_available():
        return _secret_tool_delete(profile)
    return False


def native_backend_name() -> str:
    if _is_macos():
        return "keychain"
    if _secret_tool_available():
        return "secret_tool"
    return "none"


# ────────────────────────── public API ──────────────────────────

def get_token(profile: str) -> str | None:
    """Read a token. Env wins when present; falls back to native backend."""
    _check_profile(profile)
    env = _read_env_file()
    if profile in env:
        return env[profile]
    if force_env():
        return None
    return _native_keychain_get(profile)


def set_token(profile: str, token: str, account: str | None = None) -> tuple[str, str]:
    """Store a token. Returns (backend, error_or_empty).

    backend ∈ {"keychain", "secret_tool", "env"}. On native-backend failure,
    automatically falls through to env.
    """
    _check_profile(profile)
    if force_env():
        env = _read_env_file()
        env[profile] = token
        if _write_env_file(env):
            return "env", ""
        return "env", "failed to write env file"
    ok, err = _native_keychain_set(profile, token, account)
    if ok:
        return native_backend_name(), ""
    env = _read_env_file()
    env[profile] = token
    if _write_env_file(env):
        return "env", f"native backend failed ({err.strip()[:80]}); stored in {env_file_path()}"
    return "env", f"native backend failed AND env write failed; tried: {err.strip()[:80]}"


def delete_token(profile: str) -> list[str]:
    """Remove from BOTH backends. Returns list of removed-from labels."""
    _check_profile(profile)
    removed: list[str] = []
    env = _read_env_file()
    if profile in env:
        del env[profile]
        if _write_env_file(env):
            removed.append("env")
    if _native_keychain_delete(profile):
        removed.append(native_backend_name())
    return removed


def list_tokens() -> dict[str, str]:
    """Return {profile: backend} for all known tokens."""
    out: dict[str, str] = {}
    if not force_env():
        # Probe known names from env file + caam filesystem
        from cmaxctl import caam
        seen = set(_read_env_file().keys()) | set(caam.filesystem_profiles())
        for p in seen:
            try:
                if _native_keychain_get(p):
                    out[p] = native_backend_name()
            except ValueError:
                pass
    for p in _read_env_file():
        out.setdefault(p, "env")
    return out


def storage_status() -> dict:
    """Snapshot for `cmax doctor`."""
    return {
        "env_file": str(env_file_path()),
        "env_file_exists": env_file_path().exists(),
        "force_env": force_env(),
        "native_backend": native_backend_name(),
        "tokens": list_tokens(),
    }


# ────────────────────────── CLI ──────────────────────────

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m cmaxctl.secrets {get|set|delete|list|status} [args...]",
              file=sys.stderr)
        return 64
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "get":
        if not args:
            return 64
        v = get_token(args[0])
        if v is None:
            print(json.dumps({"ok": False, "profile": args[0]}))
            return 1
        print(v, end="")
        return 0
    if cmd == "set":
        if len(args) < 2:
            return 64
        backend, err = set_token(args[0], args[1], args[2] if len(args) > 2 else None)
        print(json.dumps({"backend": backend, "error": err}))
        return 0 if not err.startswith("native backend failed AND") else 1
    if cmd == "delete":
        if not args:
            return 64
        removed = delete_token(args[0])
        print(json.dumps({"removed_from": removed}))
        return 0
    if cmd == "list":
        print(json.dumps(list_tokens(), indent=2))
        return 0
    if cmd == "status":
        print(json.dumps(storage_status(), indent=2))
        return 0
    print(f"unknown: {cmd}", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
