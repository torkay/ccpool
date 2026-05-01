"""Integration: ccpool runs degraded but functional with no caam, no claude.

Covers Phase 2 acceptance gate for Linux container CI: when nothing is
installed except python+ccpool, the CLI still:

  * `statusline`   → emits valid JSON, no crash
  * `migrate detect` → reports detected=False on a fresh container
  * `doctor --json`  → returns findings (degraded), exits 1 (HIGH for missing
                       caam) but never raises
  * `inventory`      → snapshot is JSON-shaped

This is platform-neutral; it runs on macOS too, but the CI lane that matters
is Linux + Ubuntu containers, where it is the primary parity check.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(monkeypatch, *args, expected_rc=None):
    """Invoke `python -m ccpool.cli <args>` with the conftest-isolated $HOME."""
    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo)
    # Force PATH to a deterministic minimum so caam + claude are both absent.
    env["PATH"] = "/usr/bin:/bin"
    proc = subprocess.run(
        [sys.executable, "-m", "ccpool.cli", *args],
        capture_output=True, text=True, env=env, timeout=15,
    )
    if expected_rc is not None:
        assert proc.returncode == expected_rc, (
            f"rc={proc.returncode} stderr={proc.stderr!r} stdout={proc.stdout!r}"
        )
    return proc


def test_statusline_emits_valid_json_when_no_binaries(monkeypatch):
    proc = _run(monkeypatch, "statusline")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["version"] == 1
    assert payload["profile"] is None
    assert payload["five_hour_pct"] is None
    assert payload["seven_day_pct"] is None
    assert payload["saturated"] is False
    assert payload["degraded"] is False


def test_statusline_short_does_not_crash(monkeypatch):
    proc = _run(monkeypatch, "statusline", "--short")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.strip()
    assert out, "expected non-empty short output"
    # Format is "<emoji> <profile-or-em-dash>"; either is fine, just non-empty.


def test_migrate_detect_clean_returns_no_v0(monkeypatch):
    proc = _run(monkeypatch, "migrate", "detect")
    # rc=1 when not detected (per migrate.py main contract).
    assert proc.returncode == 1, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["detected"] is False
    assert payload["signals"] == []


def test_doctor_json_returns_findings_no_crash(monkeypatch):
    proc = _run(monkeypatch, "doctor", "--json")
    # rc 1 (HIGH) is expected when caam is absent.
    assert proc.returncode in (0, 1, 2), proc.stderr
    payload = json.loads(proc.stdout)
    assert "findings" in payload
    assert "highest_severity" in payload
    # caam_missing or similar must show up.
    codes = {f.get("code") for f in payload["findings"]}
    assert any("caam" in (c or "").lower() for c in codes), (
        f"expected a caam-related finding, got {codes}"
    )


def test_inventory_emits_json_snapshot(monkeypatch):
    proc = _run(monkeypatch, "inventory")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    # Sanity: the snapshot should at minimum carry profile + storage keys.
    assert "profiles" in payload or "profile_summary" in payload or "storage" in payload


def test_version_prints_ccpool_version(monkeypatch):
    proc = _run(monkeypatch, "version")
    assert proc.returncode == 0, proc.stderr
    assert "ccpool" in proc.stdout.lower()
