"""ccpool/usage.py — Anthropic /api/oauth/usage client.

Reads the per-profile access token (provisioned by `caam login`/`claude auth login`),
hits the undocumented endpoint, returns parsed Usage. ADR-0007 documents the
fragility tradeoff and tier-2/3 fallback path.

5-second file cache to keep the picker fast and respect implicit rate limits.

Stdlib only.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ccpool import caam, config, paths

CACHE_TTL_S = 5
ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"
USER_AGENT = f"ccpool/{__import__('ccpool')._version.__version__}"
HTTP_TIMEOUT = 5.0


@dataclass
class Window:
    utilization: float
    resets_at: str


@dataclass
class Usage:
    profile: str
    fetched_at: float
    five_hour: Window | None = None
    seven_day: Window | None = None
    seven_day_sonnet: Window | None = None
    extra_usage_pct: float | None = None
    extra_usage_currency: str | None = None
    extra_usage_used_dollars: float | None = None
    extra_usage_limit_dollars: float | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Usage:
        for k in ("five_hour", "seven_day", "seven_day_sonnet"):
            v = d.get(k)
            if isinstance(v, dict):
                d[k] = Window(**v)
            elif v is None:
                d[k] = None
        # Tolerate stale cache shapes
        for legacy in ("seven_day_opus", "extra_usage_used", "extra_usage_limit"):
            d.pop(legacy, None)
        return cls(**d)


def _set_degraded(reason: str) -> None:
    p = paths.degraded_flag_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(reason)
    except OSError:
        pass


def _load_cache() -> dict:
    try:
        return json.loads(paths.usage_cache_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    p = paths.usage_cache_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, indent=2, default=str))
    except OSError:
        pass


def _read_token_from_creds_file(path: Path) -> str | None:
    try:
        d = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    inner = d.get("claudeAiOauth") if isinstance(d, dict) else None
    if isinstance(inner, dict):
        return inner.get("accessToken") or inner.get("access_token")
    if isinstance(d, dict):
        return d.get("accessToken") or d.get("access_token")
    return None


def _read_token_from_default_keychain() -> str | None:
    """Fallback used only for the un-profiled case (operator's primary login)."""
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.strip()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return None
    inner = d.get("claudeAiOauth") or d
    return inner.get("accessToken") or inner.get("access_token")


def _resolve_token(profile: str | None, cfg: config.Config | None = None) -> str | None:
    if profile:
        env = caam.caam_env_for(profile, cfg)
        if env and env.get("CLAUDE_CONFIG_DIR"):
            cred_path = Path(env["CLAUDE_CONFIG_DIR"]).expanduser() / ".credentials.json"
            if cred_path.exists():
                tok = _read_token_from_creds_file(cred_path)
                if tok:
                    return tok
        return None  # never fall back to default for a named profile
    return _read_token_from_default_keychain()


def _fetch_raw(token: str) -> dict | None:
    req = urllib.request.Request(
        ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": BETA_HEADER,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            body = ""
        _set_degraded(f"oauth/usage HTTP {exc.code}: {body}")
        return None
    except (urllib.error.URLError, TimeoutError, ConnectionError,
            json.JSONDecodeError, OSError) as exc:
        _set_degraded(f"oauth/usage transport: {exc}")
        return None


def _parse(raw: dict, profile: str) -> Usage:
    def w(key: str) -> Window | None:
        v = raw.get(key)
        if isinstance(v, dict) and "utilization" in v:
            return Window(
                utilization=float(v.get("utilization") or 0.0),
                resets_at=str(v.get("resets_at") or ""),
            )
        return None

    extra = raw.get("extra_usage") or {}
    used_cents = extra.get("used_credits")
    limit_cents = extra.get("monthly_limit")
    return Usage(
        profile=profile,
        fetched_at=time.time(),
        five_hour=w("five_hour"),
        seven_day=w("seven_day"),
        seven_day_sonnet=w("seven_day_sonnet"),
        extra_usage_pct=float(extra.get("utilization")) if extra.get("utilization") is not None else None,
        extra_usage_currency=extra.get("currency"),
        extra_usage_used_dollars=(used_cents / 100.0) if used_cents is not None else None,
        extra_usage_limit_dollars=(limit_cents / 100.0) if limit_cents is not None else None,
        raw=raw,
    )


def fetch(profile: str | None = None, *, force: bool = False,
          cfg: config.Config | None = None) -> Usage | None:
    """Fetch usage for a profile. Returns None on auth/transport failure.
    `profile=None` uses the default keychain entry."""
    cache_key = profile or "__default__"
    cache = _load_cache()
    cached = cache.get(cache_key)
    if not force and cached:
        try:
            u = Usage.from_dict(dict(cached))
            ttl = cfg.picker.usage_cache_ttl_s if cfg else CACHE_TTL_S
            if time.time() - u.fetched_at < ttl:
                return u
        except (TypeError, KeyError):
            pass
    tok = _resolve_token(profile, cfg)
    if not tok:
        return None
    raw = _fetch_raw(tok)
    if raw is None:
        return None
    usage = _parse(raw, profile or "__default__")
    cache[cache_key] = usage.to_dict()
    _save_cache(cache)
    return usage


def fetch_all(profiles: list[str], *, force: bool = False,
              cfg: config.Config | None = None) -> dict[str, Usage | None]:
    """Parallel fetch across profiles. Cold-cache fetches add up otherwise
    (200-400ms each); ThreadPool keeps total wall-time bounded."""
    if not profiles:
        return {}
    if len(profiles) == 1:
        p = profiles[0]
        return {p: fetch(p, force=force, cfg=cfg)}
    with ThreadPoolExecutor(max_workers=min(len(profiles), 6)) as pool:
        futures = {p: pool.submit(fetch, p, force=force, cfg=cfg) for p in profiles}
        return {p: f.result() for p, f in futures.items()}


def projected_endwindow_pct(u: Usage, *, in_flight_extra_pct: float = 0.0) -> float:
    """Project end-of-window utilization assuming current burn continues."""
    if u.five_hour is None:
        return 0.0
    return u.five_hour.utilization + in_flight_extra_pct


# ────────────────────────── CLI ──────────────────────────

def _cli_fetch(args: list[str]) -> int:
    profile = args[0] if args and not args[0].startswith("-") else None
    force = "--force" in args
    u = fetch(profile, force=force)
    if not u:
        print(json.dumps({"ok": False, "profile": profile or "__default__"}))
        return 1
    print(json.dumps(u.to_dict(), indent=2, default=str))
    return 0


def _cli_all(args: list[str]) -> int:
    if args and not args[0].startswith("-"):
        profiles = [a for a in args if not a.startswith("-")]
    else:
        profiles = [line.strip() for line in sys.stdin if line.strip()]
    out = {p: (u.to_dict() if u else None) for p, u in fetch_all(profiles).items()}
    print(json.dumps(out, indent=2, default=str))
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m ccpool.usage {fetch [profile] | all <profile1> ...} [--force]",
              file=sys.stderr)
        return 2
    cmd, *args = sys.argv[1:]
    if cmd == "fetch":
        return _cli_fetch(args)
    if cmd == "all":
        return _cli_all(args)
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
