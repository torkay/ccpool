"""Unit tests for ccpool.identity — fingerprint vs identity-marker semantics."""
from __future__ import annotations

import sys


def _fresh():
    for mod in ("ccpool.identity",):
        sys.modules.pop(mod, None)
    from ccpool import identity
    return identity


def test_fingerprint_drifts_when_utilization_drifts():
    identity = _fresh()
    a = {
        "five_hour": {"utilization": 42.0},
        "seven_day": {"utilization": 71.0, "resets_at": "2026-05-04T00:00:00Z"},
        "extra_usage": {"used_credits": 0, "monthly_limit": 200, "currency": "USD"},
    }
    b = {
        "five_hour": {"utilization": 42.5},
        "seven_day": {"utilization": 71.0, "resets_at": "2026-05-04T00:00:00Z"},
        "extra_usage": {"used_credits": 0, "monthly_limit": 200, "currency": "USD"},
    }
    assert identity.token_fingerprint(a) != identity.token_fingerprint(b)


def test_identity_marker_stable_across_drift():
    identity = _fresh()
    a = {
        "five_hour": {"utilization": 42.0},
        "seven_day": {"utilization": 71.0, "resets_at": "2026-05-04T00:00:00Z"},
        "extra_usage": {"used_credits": 0, "monthly_limit": 200, "currency": "USD"},
    }
    b = dict(a)
    b["five_hour"] = {"utilization": 90.0}
    b["seven_day"] = {**a["seven_day"], "utilization": 95.0}
    assert identity.account_identity_marker(a) == identity.account_identity_marker(b)


def test_identity_marker_distinguishes_accounts():
    identity = _fresh()
    a = {
        "seven_day": {"resets_at": "2026-05-04T00:00:00Z"},
        "extra_usage": {"monthly_limit": 200, "currency": "USD"},
    }
    b = {
        "seven_day": {"resets_at": "2026-05-09T00:00:00Z"},
        "extra_usage": {"monthly_limit": 200, "currency": "USD"},
    }
    assert identity.account_identity_marker(a) != identity.account_identity_marker(b)


def test_validate_oauth_token_handles_none():
    identity = _fresh()
    assert identity.validate_oauth_token("") is None
    assert identity.validate_oauth_token("   ") is None


def test_marker_returns_none_for_unstructured_input():
    identity = _fresh()
    assert identity.account_identity_marker(None) is None
    assert identity.account_identity_marker("not a dict") is None
    assert identity.token_fingerprint(None) is None
