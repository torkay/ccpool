"""cmaxctl/identity.py — token validation + per-account identity markers.

Used by `cmax setup` to detect "operator signed into the same account twice"
(footgun: rotation across two profiles that share an account is no rotation).

Two derived identifiers:

  - `fingerprint`  — distinguishing across accounts. Drifts second-to-second
                     (utilization fields), so use only when you're comparing
                     two snapshots taken at the same time.
  - `identity_marker` — STABLE across token issuance for the same account.
                        Built from 7-day reset boundary (keyed to account
                        creation), monthly cap, and currency.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from cmaxctl import caam, config

ENDPOINT = "https://api.anthropic.com/api/oauth/usage"
BETA_HEADER = "oauth-2025-04-20"


def validate_oauth_token(token: str) -> dict | None:
    """Hit /api/oauth/usage with `token`. Returns parsed JSON on 200, else None.

    Note: long-lived setup-tokens have `user:inference` scope and 403 here.
    Per-profile access tokens (`user:profile` scope) succeed.
    """
    if not token or not token.strip():
        return None
    req = urllib.request.Request(
        ENDPOINT,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "anthropic-beta": BETA_HEADER,
            "User-Agent": "cmaxctl/identity",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, ConnectionError, json.JSONDecodeError, OSError):
        return None


def token_fingerprint(usage_response: dict | None) -> str | None:
    """Distinguish two snapshots; same account at the same instant returns same fp."""
    if not isinstance(usage_response, dict):
        return None
    extra = usage_response.get("extra_usage") or {}
    five = (usage_response.get("five_hour") or {}).get("utilization")
    seven = (usage_response.get("seven_day") or {}).get("utilization")
    return (f"5h={five}|7d={seven}|used={extra.get('used_credits')}"
            f"|limit={extra.get('monthly_limit')}|cur={extra.get('currency')}")


def account_identity_marker(usage_response: dict | None) -> str | None:
    """Stable per-account identifier — same across two tokens of one account,
    different across accounts.

    Empirically: utilization fields drift second-to-second; reset_at and
    monthly_limit don't.
    """
    if not isinstance(usage_response, dict):
        return None
    seven = (usage_response.get("seven_day") or {}).get("resets_at") or ""
    extra = usage_response.get("extra_usage") or {}
    return (f"7d_reset={seven}|cap={extra.get('monthly_limit')}"
            f"|cur={extra.get('currency')}")


def profile_identity_marker(profile: str,
                            cfg: config.Config | None = None) -> str | None:
    """Read per-profile access token from the caam-isolated CLAUDE_CONFIG_DIR,
    hit /api/oauth/usage, return the identity marker. Used by setup to detect
    same-account-twice."""
    env = caam.caam_env_for(profile, cfg)
    if not env or not env.get("CLAUDE_CONFIG_DIR"):
        return None
    creds_path = Path(env["CLAUDE_CONFIG_DIR"]).expanduser() / ".credentials.json"
    if not creds_path.exists():
        return None
    try:
        data = json.loads(creds_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    inner = data.get("claudeAiOauth") or data
    tok = (inner or {}).get("accessToken") or (inner or {}).get("access_token")
    if not tok:
        return None
    response = validate_oauth_token(tok)
    return account_identity_marker(response)


# ────────────────────────── CLI ──────────────────────────

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m cmaxctl.identity {validate <token> | marker <profile>}",
              file=sys.stderr)
        return 64
    cmd = sys.argv[1]
    args = sys.argv[2:]
    if cmd == "validate":
        if not args:
            print(json.dumps({"ok": False, "reason": "no_token"}))
            return 1
        u = validate_oauth_token(args[0])
        if u is None:
            print(json.dumps({"ok": False, "reason": "invalid_or_unreachable"}))
            return 1
        print(json.dumps({
            "ok": True,
            "fingerprint": token_fingerprint(u),
            "five_hour_pct": (u.get("five_hour") or {}).get("utilization"),
            "seven_day_pct": (u.get("seven_day") or {}).get("utilization"),
        }))
        return 0
    if cmd == "marker":
        if not args:
            return 64
        m = profile_identity_marker(args[0])
        if not m:
            return 1
        print(m)
        return 0
    print(f"unknown: {cmd}", file=sys.stderr)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())
