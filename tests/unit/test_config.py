"""Unit tests for cmaxctl.config — schema, validation, round-trip."""
from __future__ import annotations

import sys


def _fresh():
    for mod in ("cmaxctl.paths", "cmaxctl.config"):
        sys.modules.pop(mod, None)
    from cmaxctl import config
    return config


def test_default_config_passes_validation_modulo_warnings():
    config = _fresh()
    cfg = config.Config()
    findings = config.validate_config(cfg)
    errors = config.hard_errors(findings)
    # An empty default has 0 profiles → 1 warning, 0 errors.
    assert errors == [], f"unexpected errors: {errors}"


def test_threshold_ordering_enforced():
    config = _fresh()
    cfg = config.Config()
    cfg.picker.soft_threshold_pct = 95.0
    cfg.picker.hard_threshold_pct = 90.0
    findings = config.validate_config(cfg)
    msgs = [f.field for f in findings if f.severity == "error"]
    assert "picker.hard_threshold_pct" in msgs


def test_duplicate_profile_names_rejected():
    config = _fresh()
    cfg = config.Config()
    cfg.profiles = [
        config.Profile(name="dup"),
        config.Profile(name="dup"),
    ]
    findings = config.validate_config(cfg)
    errors = [f for f in findings if f.severity == "error"]
    assert any("duplicate" in f.message for f in errors)


def test_invalid_profile_name_rejected():
    config = _fresh()
    cfg = config.Config()
    cfg.profiles = [config.Profile(name="bad name with spaces")]
    findings = config.validate_config(cfg)
    errors = [f for f in findings if f.severity == "error"]
    assert any("invalid profile name" in f.message for f in errors)


def test_invalid_email_warns_only():
    config = _fresh()
    cfg = config.Config()
    cfg.profiles = [config.Profile(name="ok", email="not-an-email")]
    findings = config.validate_config(cfg)
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    assert errors == []
    assert any("doesn't look like an email" in f.message for f in warnings)


def test_round_trip_render_then_load(tmp_path):
    config = _fresh()
    cfg = config.Config()
    cfg.meta.repo_owner = "torkay"
    cfg.profiles = [
        config.Profile(name="alpha", email="a@b.co", description="primary"),
        config.Profile(name="beta", email="c@d.co"),
    ]
    cfg.picker.soft_threshold_pct = 80.0
    cfg.picker.hard_threshold_pct = 92.0
    cfg.notify.command = ["/usr/bin/true", "--flag"]

    out_path = tmp_path / "out.toml"
    written = config.write(cfg, out_path)
    assert written == out_path
    loaded = config.load_from_path(out_path)

    assert loaded.meta.repo_owner == "torkay"
    assert [p.name for p in loaded.profiles] == ["alpha", "beta"]
    assert loaded.picker.hard_threshold_pct == 92.0
    assert loaded.notify.command == ["/usr/bin/true", "--flag"]


def test_load_missing_returns_defaults():
    config = _fresh()
    cfg = config.load()
    assert cfg.profiles == []
    assert cfg.source_path is None


def test_notify_command_string_rejected():
    """Security: notify.command must be a list, never a shell string.

    A bare string in TOML would tempt callers to pass it to `shell=True` which
    would be a command-injection footgun. _coerce should drop it and produce
    an empty list.
    """
    config = _fresh()
    raw = {"notify": {"command": "echo hello"}}
    cfg = config._coerce(raw)
    assert cfg.notify.command == []


def test_schema_version_drift_is_hard_error():
    config = _fresh()
    cfg = config.Config()
    cfg.meta.schema_version = 99
    findings = config.validate_config(cfg)
    errors = config.hard_errors(findings)
    assert any(f.field == "meta.schema_version" for f in errors)
