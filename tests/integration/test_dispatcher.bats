#!/usr/bin/env bats
# Surface tests for `bin/cmax` argument routing.
#
# Covers the dispatcher's branching: `is_subcommand` matching, help/version
# wiring, default-mode fall-through to claude when no subcommand recognised.

load 'test_helper'

setup() {
  cmax_setup_env
}

teardown() {
  cmax_teardown_env
}

@test "cmax help prints subcommand list" {
  run "${CMAX}" help
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"cmax setup"* ]]
  [[ "${output}" == *"cmax doctor"* ]]
  [[ "${output}" == *"cmax statusline"* ]]
}

@test "cmax --help routes to help" {
  run "${CMAX}" --help
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"cmax setup"* ]]
}

@test "cmax version prints component versions" {
  run "${CMAX}" version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"cmaxctl"* ]]
}

@test "cmax with unknown first arg falls through to default mode (exec claude)" {
  # No caam available → should exec claude with the args
  unset CMAX_MOCK_CAAM_PROFILES
  rm -f "${FIXTURES_BIN}/caam.disabled" 2>/dev/null
  # Hide caam from PATH so default-mode does the no-caam fall-through
  export PATH="/usr/bin:/bin"
  # claude mock prints its version
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CMAX}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
}

@test "cmax with no args, no caam, falls through to default mode" {
  export PATH="/usr/bin:/bin"
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CMAX}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
}
