"""ccpool/blocks.py — local-transcript 5h-block estimator.

Replaces ccusage as a fallback signal source. Parses JSONL transcripts under
`$CLAUDE_CONFIG_DIR/projects/**/*.jsonl` (or the profile's caam-isolated
config dir) and computes the active 5-hour block's token consumption.

Algorithm matches ccusage `blocks --active`:
1. Collect assistant entries with `message.usage` and a `timestamp`.
2. Sort by timestamp.
3. Walk forward; new block at first entry after >5h gap or when 5h elapsed.
4. Active block = the one whose end >= now.
5. Burn rate = tokens_so_far / minutes_elapsed.
6. Projected total = burn_rate * 300.

Used only when /api/oauth/usage returns None.
Stdlib only.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ccpool import caam, config, paths

BLOCK_HOURS = 5
BLOCK_DURATION = timedelta(hours=BLOCK_HOURS)
INACTIVITY_GAP = timedelta(hours=BLOCK_HOURS)


@dataclass
class ActiveBlock:
    start_iso: str
    end_iso: str
    is_active: bool
    minutes_elapsed: float
    minutes_remaining: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    total_tokens: int
    burn_tokens_per_min: float
    projected_total_tokens: int
    entry_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def _resolve_projects_dir(profile: str | None,
                          cfg: config.Config | None = None) -> Path:
    if not profile:
        return paths.claude_projects_dir()
    env = caam.caam_env_for(profile, cfg)
    if env and env.get("CLAUDE_CONFIG_DIR"):
        pd = Path(env["CLAUDE_CONFIG_DIR"]).expanduser() / "projects"
        if pd.exists():
            return pd
    return paths.claude_projects_dir()


def _iter_assistant_usage(projects_dir: Path, *, since: datetime | None = None):
    if not projects_dir.exists():
        return
    cutoff_ts = since.timestamp() if since else 0.0
    for jsonl in projects_dir.rglob("*.jsonl"):
        try:
            if jsonl.stat().st_mtime < cutoff_ts:
                continue
        except OSError:
            continue
        try:
            with jsonl.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if d.get("type") != "assistant":
                        continue
                    msg = d.get("message")
                    if not isinstance(msg, dict):
                        continue
                    usage = msg.get("usage")
                    if not isinstance(usage, dict):
                        continue
                    ts_str = d.get("timestamp")
                    if not isinstance(ts_str, str):
                        continue
                    try:
                        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    yield ts_dt, usage
        except OSError:
            continue


def _block_start(ts: datetime) -> datetime:
    """Round down to hour boundary in UTC (ccusage parity)."""
    return ts.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def active_block(profile: str | None = None, *, lookback_hours: int = 12,
                 cfg: config.Config | None = None) -> ActiveBlock | None:
    """Compute the currently-active 5h block for a profile."""
    projects_dir = _resolve_projects_dir(profile, cfg)
    now = datetime.now(UTC)
    since = now - timedelta(hours=lookback_hours)
    entries = sorted(_iter_assistant_usage(projects_dir, since=since), key=lambda x: x[0])
    if not entries:
        return None

    current_start: datetime | None = None
    current_end: datetime | None = None
    last_ts: datetime | None = None
    block_entries: list[tuple[datetime, dict]] = []

    for ts, usage in entries:
        ts_utc = ts.astimezone(UTC)
        if current_start is None:
            current_start = _block_start(ts_utc)
            current_end = current_start + BLOCK_DURATION
            block_entries = [(ts_utc, usage)]
            last_ts = ts_utc
            continue
        gap = ts_utc - last_ts if last_ts else timedelta(0)
        if ts_utc >= current_end or gap >= INACTIVITY_GAP:
            current_start = _block_start(ts_utc)
            current_end = current_start + BLOCK_DURATION
            block_entries = [(ts_utc, usage)]
        else:
            block_entries.append((ts_utc, usage))
        last_ts = ts_utc

    if current_start is None or current_end is None:
        return None

    is_active = now < current_end
    if not is_active and (last_ts is None or now - last_ts >= INACTIVITY_GAP):
        return None

    inp = out = cr = cc = 0
    for _, u in block_entries:
        inp += int(u.get("input_tokens") or 0)
        out += int(u.get("output_tokens") or 0)
        cr += int(u.get("cache_read_input_tokens") or 0)
        cc += int(u.get("cache_creation_input_tokens") or 0)
    total = inp + out + cr + cc

    elapsed_s = max((now - current_start).total_seconds(), 1.0)
    elapsed_min = elapsed_s / 60.0
    remaining_min = max((current_end - now).total_seconds() / 60.0, 0.0)
    burn = total / elapsed_min if elapsed_min > 0 else 0.0
    projected = int(burn * 60 * BLOCK_HOURS) if is_active else total

    return ActiveBlock(
        start_iso=current_start.isoformat(),
        end_iso=current_end.isoformat(),
        is_active=is_active,
        minutes_elapsed=round(elapsed_min, 1),
        minutes_remaining=round(remaining_min, 1),
        input_tokens=inp,
        output_tokens=out,
        cache_read_tokens=cr,
        cache_creation_tokens=cc,
        total_tokens=total,
        burn_tokens_per_min=round(burn, 1),
        projected_total_tokens=projected,
        entry_count=len(block_entries),
    )


# ────────────────────────── CLI ──────────────────────────

def main() -> int:
    args = sys.argv[1:]
    profile = None
    if args and not args[0].startswith("-"):
        profile = args[0]
    block = active_block(profile)
    if not block:
        print(json.dumps({"ok": False, "profile": profile or "__default__"}))
        return 1
    print(json.dumps({"ok": True, "profile": profile or "__default__", "block": block.to_dict()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
