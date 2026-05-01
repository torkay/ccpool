#!/usr/bin/env bats
# End-to-end walk per plan §12.3.
#
# Fixture: temp $HOME + mocked caam shim + mocked claude shim
# Walk: seed config → status → doctor → usage → disable → unwrapped → enable
# Network: none — all stubbed
# OAuth:   none real

load '../integration/test_helper'

setup() {
  ccpool_setup_env
}

teardown() {
  ccpool_teardown_env
}

@test "e2e: seed → status → doctor → usage → disable → enable" {
  # 1. Seed config + caam profiles + tokens
  ccpool_seed_config myowner
  ccpool_seed_caam_profile alpha
  ccpool_seed_caam_profile beta
  ccpool_seed_token alpha
  ccpool_seed_token beta

  # 2. Status — both profiles visible
  run "${CCPOOL}" status
  [[ "${output}" == *"alpha"* ]]
  [[ "${output}" == *"beta"* ]]

  # 3. Doctor — JSON well-formed
  run "${CCPOOL}" doctor --json
  python3 -c "
import json
d = json.loads('''${output}''')
assert 'findings' in d
"

  # 4. Usage — no traceback even if endpoint unreachable
  run "${CCPOOL}" usage --json
  [[ "${output}" != *"Traceback"* ]]

  # 5. Disable — flag written, default mode skips rotation
  run "${CCPOOL}" disable
  [ "${status}" -eq 0 ]
  [ -f "${XDG_DATA_HOME}/ccpool/disabled" ]

  # 6. Default mode under disabled goes straight to claude
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CCPOOL}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]

  # 7. Enable — flag removed
  run "${CCPOOL}" enable
  [ "${status}" -eq 0 ]
  [ ! -f "${XDG_DATA_HOME}/ccpool/disabled" ]
}

@test "e2e: statusline reflects state after seeding" {
  ccpool_seed_config
  ccpool_seed_caam_profile alpha
  ccpool_seed_token alpha

  run "${CCPOOL}" statusline
  [ "${status}" -eq 0 ]
  python3 -c "
import json
d = json.loads('''${output}''')
assert d['version'] == 1
assert isinstance(d['saturated'], bool)
assert isinstance(d['degraded'], bool)
"
}

@test "e2e: migrate detect against fresh tree reports detected=false" {
  run "${CCPOOL}" migrate detect
  python3 -c "
import json
d = json.loads('''${output}''')
# Fresh tmp HOME — no v0 substrate
assert d['detected'] is False, f'expected detected=false, got {d}'
"
}

@test "e2e: identity-scrub gate passes against checked-in repo" {
  # Fail loudly if Phase 1's identity-scrub regressed.
  ! grep -rE '(torrinkay|tor1|tor2|amatorri|/Users/)' \
      --include='*.py' --include='*.sh' --include='*.toml' --include=ccpool \
      "${REPO_DIR}/ccpool" "${REPO_DIR}/tests" "${REPO_DIR}/docs" "${REPO_DIR}/bin" \
    | grep -vE '(tests/fixtures|migrate.py|CHANGELOG|/__pycache__/)'
}
