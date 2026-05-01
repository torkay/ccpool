"""ccpool/config.py — TOML config loader, writer, validator.

Schema documented in `docs/REFERENCE.md` and the canonical example template
shipped at `ccpool/templates/config.toml.example`.

Stdlib only: tomllib (read; 3.11+), hand-rolled TOML writing (no `tomli_w` dep).
"""
from __future__ import annotations

import os
import re
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ccpool import paths

CURRENT_SCHEMA_VERSION = 1
PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Profile:
    name: str
    email: str = ""
    description: str = ""
    config_dir_override: str = ""


@dataclass
class PickerConfig:
    strategy_order: list[str] = field(
        default_factory=lambda: ["usage_aware", "caam_smart", "round_robin"]
    )
    soft_threshold_pct: float = 85.0
    hard_threshold_pct: float = 95.0
    usage_cache_ttl_s: int = 5


@dataclass
class WatcherConfig:
    enabled: bool = True
    interval_s: int = 300
    network_every_n: int = 6
    min_gap_s: int = 600
    dry_run: bool = False


@dataclass
class WatchdogConfig:
    enabled: bool = True
    five_hour_alert_pct: float = 85.0
    seven_day_alert_pct: float = 90.0
    extra_usage_alert_pct: float = 90.0
    prune_keep_minutes: int = 1440


@dataclass
class StorageConfig:
    backend: str = "auto"  # auto | keychain | secret_tool | env
    env_file: str = ""
    encrypt_env: bool = False
    token_age_warn_days: int = 330
    token_age_critical_days: int = 360


@dataclass
class NotifyConfig:
    command: list[str] = field(default_factory=list)
    severities: list[str] = field(default_factory=lambda: ["high", "critical"])


@dataclass
class ShellConfig:
    manage_rc_file: bool = True
    files: list[str] = field(default_factory=lambda: ["~/.zshrc", "~/.bashrc"])
    alias_claude: bool = True
    export_flags: bool = True


@dataclass
class TelemetryConfig:
    enabled: bool = False
    endpoint: str = ""
    include_errors: bool = True


@dataclass
class MetaConfig:
    schema_version: int = CURRENT_SCHEMA_VERSION
    repo_owner: str = ""  # used for plist labels; empty → paths.DEFAULT_OWNER


@dataclass
class ProviderConfig:
    name: str = "claude"  # claude | codex | gemini
    binary: str = ""  # auto-detected via $PATH if empty
    caam_bin: str = ""


@dataclass
class Config:
    meta: MetaConfig = field(default_factory=MetaConfig)
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    profiles: list[Profile] = field(default_factory=list)
    picker: PickerConfig = field(default_factory=PickerConfig)
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    watchdog: WatchdogConfig = field(default_factory=WatchdogConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    shell: ShellConfig = field(default_factory=ShellConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)

    # Where we loaded from (for diagnostics; not persisted)
    source_path: Path | None = None


# ────────────────────────── validation ──────────────────────────

class ConfigError(ValueError):
    """Raised on hard-error validation failures."""


@dataclass
class ValidationFinding:
    severity: str  # "error" | "warning"
    field: str
    message: str


def validate_config(cfg: Config) -> list[ValidationFinding]:
    """Return a list of findings. Hard errors prevent runtime; warnings don't."""
    findings: list[ValidationFinding] = []

    if cfg.meta.schema_version != CURRENT_SCHEMA_VERSION:
        findings.append(ValidationFinding(
            "error", "meta.schema_version",
            f"schema_version {cfg.meta.schema_version} != current {CURRENT_SCHEMA_VERSION}; run `ccpool migrate`",
        ))

    if not cfg.profiles:
        findings.append(ValidationFinding(
            "warning", "profiles",
            "no profiles configured — observability only, rotation needs ≥2",
        ))
    elif len(cfg.profiles) < 2:
        findings.append(ValidationFinding(
            "warning", "profiles",
            f"only {len(cfg.profiles)} profile(s) — rotation has nothing to alternate to",
        ))

    seen_names: set[str] = set()
    for i, p in enumerate(cfg.profiles):
        if not PROFILE_NAME_RE.match(p.name):
            findings.append(ValidationFinding(
                "error", f"profiles[{i}].name",
                f"invalid profile name {p.name!r}; must match {PROFILE_NAME_RE.pattern}",
            ))
        if p.name in seen_names:
            findings.append(ValidationFinding(
                "error", f"profiles[{i}].name",
                f"duplicate profile name {p.name!r}",
            ))
        seen_names.add(p.name)
        if p.email and not EMAIL_RE.match(p.email):
            findings.append(ValidationFinding(
                "warning", f"profiles[{i}].email",
                f"email {p.email!r} doesn't look like an email address",
            ))

    if cfg.picker.hard_threshold_pct <= cfg.picker.soft_threshold_pct:
        findings.append(ValidationFinding(
            "error", "picker.hard_threshold_pct",
            f"hard_threshold_pct ({cfg.picker.hard_threshold_pct}) must exceed "
            f"soft_threshold_pct ({cfg.picker.soft_threshold_pct})",
        ))

    if cfg.notify.command:
        first = cfg.notify.command[0]
        if first.startswith("/"):
            if not Path(first).expanduser().exists():
                findings.append(ValidationFinding(
                    "warning", "notify.command",
                    f"absolute path {first!r} not found",
                ))
        # PATH check requires shutil.which; tolerate missing for warn-only
        # (deferred to doctor for final verdict)

    if cfg.shell.manage_rc_file:
        # We accept the list as-is here; shell.py decides which to actually write
        if not cfg.shell.files:
            findings.append(ValidationFinding(
                "warning", "shell.files",
                "manage_rc_file=true but shell.files is empty",
            ))

    return findings


def hard_errors(findings: list[ValidationFinding]) -> list[ValidationFinding]:
    return [f for f in findings if f.severity == "error"]


# ────────────────────────── loading ──────────────────────────

def _coerce_profile(raw: dict) -> Profile:
    return Profile(
        name=str(raw.get("name", "")),
        email=str(raw.get("email", "")),
        description=str(raw.get("description", "")),
        config_dir_override=str(raw.get("config_dir_override", "")),
    )


def _coerce(raw: dict) -> Config:
    """Coerce a parsed-TOML dict into a Config dataclass with defaults."""
    cfg = Config()

    meta_raw = raw.get("meta") or {}
    cfg.meta.schema_version = int(meta_raw.get("schema_version", CURRENT_SCHEMA_VERSION))
    cfg.meta.repo_owner = str(meta_raw.get("repo_owner", ""))

    prov_raw = raw.get("provider") or {}
    cfg.provider.name = str(prov_raw.get("name", "claude"))
    cfg.provider.binary = str(prov_raw.get("binary", ""))
    cfg.provider.caam_bin = str(prov_raw.get("caam_bin", ""))

    profiles_raw = raw.get("profile") or []
    if not isinstance(profiles_raw, list):
        profiles_raw = []
    cfg.profiles = [_coerce_profile(p) for p in profiles_raw if isinstance(p, dict)]

    pick_raw = raw.get("picker") or {}
    if "strategy_order" in pick_raw and isinstance(pick_raw["strategy_order"], list):
        cfg.picker.strategy_order = [str(s) for s in pick_raw["strategy_order"]]
    cfg.picker.soft_threshold_pct = float(pick_raw.get("soft_threshold_pct", 85.0))
    cfg.picker.hard_threshold_pct = float(pick_raw.get("hard_threshold_pct", 95.0))
    cfg.picker.usage_cache_ttl_s = int(pick_raw.get("usage_cache_ttl_s", 5))

    w_raw = raw.get("watcher") or {}
    cfg.watcher.enabled = bool(w_raw.get("enabled", True))
    cfg.watcher.interval_s = int(w_raw.get("interval_s", 300))
    cfg.watcher.network_every_n = int(w_raw.get("network_every_n", 6))
    cfg.watcher.min_gap_s = int(w_raw.get("min_gap_s", 600))
    cfg.watcher.dry_run = bool(w_raw.get("dry_run", False))

    wd_raw = raw.get("watchdog") or {}
    cfg.watchdog.enabled = bool(wd_raw.get("enabled", True))
    cfg.watchdog.five_hour_alert_pct = float(wd_raw.get("five_hour_alert_pct", 85.0))
    cfg.watchdog.seven_day_alert_pct = float(wd_raw.get("seven_day_alert_pct", 90.0))
    cfg.watchdog.extra_usage_alert_pct = float(wd_raw.get("extra_usage_alert_pct", 90.0))
    cfg.watchdog.prune_keep_minutes = int(wd_raw.get("prune_keep_minutes", 1440))

    st_raw = raw.get("storage") or {}
    cfg.storage.backend = str(st_raw.get("backend", "auto"))
    cfg.storage.env_file = str(st_raw.get("env_file", ""))
    cfg.storage.encrypt_env = bool(st_raw.get("encrypt_env", False))
    cfg.storage.token_age_warn_days = int(st_raw.get("token_age_warn_days", 330))
    cfg.storage.token_age_critical_days = int(st_raw.get("token_age_critical_days", 360))

    n_raw = raw.get("notify") or {}
    cmd_raw = n_raw.get("command", [])
    if isinstance(cmd_raw, list):
        cfg.notify.command = [str(x) for x in cmd_raw]
    else:
        # Reject shell-style strings — security: avoid implicit shell interpolation
        cfg.notify.command = []
    sev_raw = n_raw.get("severities", ["high", "critical"])
    if isinstance(sev_raw, list):
        cfg.notify.severities = [str(s) for s in sev_raw]

    sh_raw = raw.get("shell") or {}
    cfg.shell.manage_rc_file = bool(sh_raw.get("manage_rc_file", True))
    files_raw = sh_raw.get("files", ["~/.zshrc", "~/.bashrc"])
    if isinstance(files_raw, list):
        cfg.shell.files = [str(f) for f in files_raw]
    cfg.shell.alias_claude = bool(sh_raw.get("alias_claude", True))
    cfg.shell.export_flags = bool(sh_raw.get("export_flags", True))

    t_raw = raw.get("telemetry") or {}
    cfg.telemetry.enabled = bool(t_raw.get("enabled", False))
    cfg.telemetry.endpoint = str(t_raw.get("endpoint", ""))
    cfg.telemetry.include_errors = bool(t_raw.get("include_errors", True))

    return cfg


def load_from_path(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(f"config not found: {path}")
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config TOML invalid in {path}: {exc}") from exc
    cfg = _coerce(raw)
    cfg.source_path = path
    return cfg


def load() -> Config:
    """Discover and load config from the first existing candidate path.

    Returns a Config with defaults if none found (callers can detect via
    `cfg.source_path is None`).
    """
    for candidate in paths.candidate_config_paths():
        if candidate.exists():
            return load_from_path(candidate)
    return Config()  # all-defaults; source_path stays None


# ────────────────────────── writing ──────────────────────────

def _toml_quote(s: str) -> str:
    """Minimal TOML string quoting. Escapes backslash, quote, control chars."""
    s = s.replace("\\", "\\\\").replace("\"", "\\\"")
    s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f"\"{s}\""


def _toml_array_strings(items: list[str]) -> str:
    return "[" + ", ".join(_toml_quote(s) for s in items) + "]"


def render_toml(cfg: Config) -> str:
    """Render Config back to TOML text. Hand-rolled — stdlib has no writer."""
    out: list[str] = []
    out.append("# ccpool configuration. Generated; safe to hand-edit.")
    out.append("# Run `ccpool doctor` to validate after changes.")
    out.append("")

    out.append("[meta]")
    out.append(f"schema_version = {cfg.meta.schema_version}")
    if cfg.meta.repo_owner:
        out.append(f"repo_owner = {_toml_quote(cfg.meta.repo_owner)}")
    out.append("")

    out.append("[provider]")
    out.append(f"name      = {_toml_quote(cfg.provider.name)}")
    out.append(f"binary    = {_toml_quote(cfg.provider.binary)}")
    out.append(f"caam_bin  = {_toml_quote(cfg.provider.caam_bin)}")
    out.append("")

    for p in cfg.profiles:
        out.append("[[profile]]")
        out.append(f"name        = {_toml_quote(p.name)}")
        out.append(f"email       = {_toml_quote(p.email)}")
        if p.description:
            out.append(f"description = {_toml_quote(p.description)}")
        if p.config_dir_override:
            out.append(f"config_dir_override = {_toml_quote(p.config_dir_override)}")
        out.append("")

    out.append("[picker]")
    out.append(f"strategy_order     = {_toml_array_strings(cfg.picker.strategy_order)}")
    out.append(f"soft_threshold_pct = {cfg.picker.soft_threshold_pct}")
    out.append(f"hard_threshold_pct = {cfg.picker.hard_threshold_pct}")
    out.append(f"usage_cache_ttl_s  = {cfg.picker.usage_cache_ttl_s}")
    out.append("")

    out.append("[watcher]")
    out.append(f"enabled         = {str(cfg.watcher.enabled).lower()}")
    out.append(f"interval_s      = {cfg.watcher.interval_s}")
    out.append(f"network_every_n = {cfg.watcher.network_every_n}")
    out.append(f"min_gap_s       = {cfg.watcher.min_gap_s}")
    out.append(f"dry_run         = {str(cfg.watcher.dry_run).lower()}")
    out.append("")

    out.append("[watchdog]")
    out.append(f"enabled               = {str(cfg.watchdog.enabled).lower()}")
    out.append(f"five_hour_alert_pct   = {cfg.watchdog.five_hour_alert_pct}")
    out.append(f"seven_day_alert_pct   = {cfg.watchdog.seven_day_alert_pct}")
    out.append(f"extra_usage_alert_pct = {cfg.watchdog.extra_usage_alert_pct}")
    out.append(f"prune_keep_minutes    = {cfg.watchdog.prune_keep_minutes}")
    out.append("")

    out.append("[storage]")
    out.append(f"backend                 = {_toml_quote(cfg.storage.backend)}")
    out.append(f"env_file                = {_toml_quote(cfg.storage.env_file)}")
    out.append(f"encrypt_env             = {str(cfg.storage.encrypt_env).lower()}")
    out.append(f"token_age_warn_days     = {cfg.storage.token_age_warn_days}")
    out.append(f"token_age_critical_days = {cfg.storage.token_age_critical_days}")
    out.append("")

    out.append("[notify]")
    out.append(f"command    = {_toml_array_strings(cfg.notify.command)}")
    out.append(f"severities = {_toml_array_strings(cfg.notify.severities)}")
    out.append("")

    out.append("[shell]")
    out.append(f"manage_rc_file = {str(cfg.shell.manage_rc_file).lower()}")
    out.append(f"files          = {_toml_array_strings(cfg.shell.files)}")
    out.append(f"alias_claude   = {str(cfg.shell.alias_claude).lower()}")
    out.append(f"export_flags   = {str(cfg.shell.export_flags).lower()}")
    out.append("")

    out.append("[telemetry]")
    out.append(f"enabled        = {str(cfg.telemetry.enabled).lower()}")
    out.append(f"endpoint       = {_toml_quote(cfg.telemetry.endpoint)}")
    out.append(f"include_errors = {str(cfg.telemetry.include_errors).lower()}")
    out.append("")

    return "\n".join(out)


def write(cfg: Config, path: Path | None = None) -> Path:
    """Write config to disk. Returns the path written.

    Atomic: write-temp + rename. Creates parent dirs as needed.
    """
    if path is None:
        path = cfg.source_path or paths.default_config_path()
    paths.ensure_config_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render_toml(cfg))
    os.replace(tmp, path)
    cfg.source_path = path
    return path


def to_dict(cfg: Config) -> dict:
    """For JSON output (e.g. `ccpool inventory --config`)."""
    d = asdict(cfg)
    d.pop("source_path", None)
    return d
