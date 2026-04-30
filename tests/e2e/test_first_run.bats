#!/usr/bin/env bats
# End-to-end walk per plan §12.3.
#
# Fixture: temp $HOME + mocked caam shim + mocked claude shim
# Walk: seed config → status → doctor → usage → disable → unwrapped → enable
# Network: none — all stubbed
# OAuth:   none real

load '../integration/test_helper'

setup() {
  cmax_setup_env
}

teardown() {
  cmax_teardown_env
}

@test "e2e: seed → status → doctor → usage → disable → enable" {
  # 1. Seed config + caam profiles + tokens
  cmax_seed_config myowner
  cmax_seed_caam_profile alpha
  cmax_seed_caam_profile beta
  cmax_seed_token alpha
  cmax_seed_token beta

  # 2. Status — both profiles visible
  run "${CMAX}" status
  [[ "${output}" == *"alpha"* ]]
  [[ "${output}" == *"beta"* ]]

  # 3. Doctor — JSON well-formed
  run "${CMAX}" doctor --json
  python3 -c "
import json
d = json.loads('''${output}''')
assert 'findings' in d
"

  # 4. Usage — no traceback even if endpoint unreachable
  run "${CMAX}" usage --json
  [[ "${output}" != *"Traceback"* ]]

  # 5. Disable — flag written, default mode skips rotation
  run "${CMAX}" disable
  [ "${status}" -eq 0 ]
  [ -f "${XDG_DATA_HOME}/cmaxctl/disabled" ]

  # 6. Default mode under disabled goes straight to claude
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CMAX}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]

  # 7. Enable — flag removed
  run "${CMAX}" enable
  [ "${status}" -eq 0 ]
  [ ! -f "${XDG_DATA_HOME}/cmaxctl/disabled" ]
}

@test "e2e: statusline reflects state after seeding" {
  cmax_seed_config
  cmax_seed_caam_profile alpha
  cmax_seed_token alpha

  run "${CMAX}" statusline
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
  run "${CMAX}" migrate detect
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
      --include='*.py' --include='*.sh' --include='*.toml' --include=cmax \
      "${REPO_DIR}/cmaxctl" "${REPO_DIR}/tests" "${REPO_DIR}/docs" "${REPO_DIR}/bin" \
    | grep -vE '(tests/fixtures|migrate.py|CHANGELOG|/__pycache__/)'
}
