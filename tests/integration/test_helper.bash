# Shared bats helpers for cmaxctl integration tests.
#
# Provides:
#   * REPO_DIR / CMAX / FIXTURES_BIN — common path constants
#   * cmax_setup_env — isolates HOME + XDG, prepends mock binaries to PATH,
#     forces env-only secret backend
#   * cmax_seed_config — drops a minimal valid config.toml in $XDG_CONFIG_HOME
#   * cmax_seed_caam_profile — pre-seeds a caam profile dir with .credentials.json
#
# These run inside bats' `setup()` so each test gets a fresh tmp tree.

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CMAX="${REPO_DIR}/bin/cmax"
FIXTURES_BIN="${REPO_DIR}/tests/fixtures/bin"

cmax_setup_env() {
  TEST_HOME="$(mktemp -d -t cmax-bats.XXXXXX)"
  export HOME="${TEST_HOME}"
  export USER="${USER:-tester}"
  export XDG_CONFIG_HOME="${TEST_HOME}/.config"
  export XDG_DATA_HOME="${TEST_HOME}/.local/share"
  export XDG_CACHE_HOME="${TEST_HOME}/.cache"
  mkdir -p "${XDG_CONFIG_HOME}/cmaxctl" \
           "${XDG_DATA_HOME}/cmaxctl" \
           "${XDG_DATA_HOME}/caam" \
           "${XDG_CACHE_HOME}/cmaxctl"

  # Force env-only secret backend so tests never touch the real keychain.
  export CMAXCTL_FORCE_ENV_STORAGE=1
  export CAAM_FORCE_ENV_STORAGE=1

  # Mocks first on PATH; keep system tools (python3, awk, grep, …) reachable.
  export PATH="${FIXTURES_BIN}:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"

  # Force `python3` to the host interpreter so `cli()` finds cmaxctl.
  export CMAX_PY="$(command -v python3 || echo /usr/bin/python3)"
  export PYTHONPATH="${REPO_DIR}:${PYTHONPATH:-}"

  # Mock-binary defaults — individual tests can override.
  export CMAX_MOCK_CAAM_PROFILES="alpha,beta"
  export CMAX_MOCK_CAAM_DIR="${XDG_DATA_HOME}/caam"
}

cmax_teardown_env() {
  if [[ -n "${TEST_HOME:-}" && -d "${TEST_HOME}" && "${TEST_HOME}" == /tmp/* ]]; then
    rm -rf "${TEST_HOME}"
  fi
}

cmax_seed_config() {
  local owner="${1:-test}"
  cat > "${XDG_CONFIG_HOME}/cmaxctl/config.toml" <<EOF
[meta]
schema_version = 1
repo_owner = "${owner}"

[provider]
name = "claude"

[[profile]]
name = "alpha"
email = "tester+alpha@example.com"

[[profile]]
name = "beta"
email = "tester+beta@example.com"

[picker]
strategy_order = ["usage_aware", "caam_smart", "round_robin"]
soft_threshold_pct = 85.0
hard_threshold_pct = 95.0
usage_cache_ttl_s = 5

[watcher]
enabled = false
interval_s = 300
network_every_n = 6
min_gap_s = 600
dry_run = false

[watchdog]
enabled = false
five_hour_alert_pct = 85.0
seven_day_alert_pct = 90.0
extra_usage_alert_pct = 90.0
prune_keep_minutes = 1440

[storage]
backend = "env"
encrypt_env = false
token_age_warn_days = 330
token_age_critical_days = 360

[notify]
command = []
severities = ["high", "critical"]

[shell]
manage_rc_file = false
files = []
alias_claude = false
export_flags = false

[telemetry]
enabled = false
EOF
}

cmax_seed_caam_profile() {
  # Match production caam layout: per-profile xdg_config/claude-code wrapper.
  # See cmaxctl.paths.caam_profile_creds_path.
  local profile="$1"
  local d="${XDG_DATA_HOME}/caam/profiles/claude/${profile}/xdg_config/claude-code"
  mkdir -p "${d}"
  cat > "${d}/.credentials.json" <<'EOF'
{"claudeAiOauth":{"accessToken":"mock-access-token","refreshToken":"mock-refresh","scopes":["user:profile"]}}
EOF
}

cmax_seed_token() {
  local profile="$1" tok="${2:-sk-ant-oat01-mock}"
  local env_file="${XDG_DATA_HOME}/cmaxctl/tokens.env"
  printf 'CMAXCTL_TOKEN_%s=%s\n' "${profile}" "${tok}" >> "${env_file}"
  chmod 600 "${env_file}"
}
