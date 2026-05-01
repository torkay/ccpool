#!/usr/bin/env bats
# Surface tests for `bin/ccpool` argument routing.
#
# Covers the dispatcher's branching: `is_subcommand` matching, help/version
# wiring, default-mode fall-through to claude when no subcommand recognised.

load 'test_helper'

setup() {
  ccpool_setup_env
}

teardown() {
  ccpool_teardown_env
}

@test "ccpool help prints subcommand list" {
  run "${CCPOOL}" help
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"ccpool setup"* ]]
  [[ "${output}" == *"ccpool doctor"* ]]
  [[ "${output}" == *"ccpool statusline"* ]]
}

@test "ccpool --help routes to help" {
  run "${CCPOOL}" --help
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"ccpool setup"* ]]
}

@test "ccpool version prints component versions" {
  run "${CCPOOL}" version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"ccpool"* ]]
}

@test "ccpool with unknown first arg falls through to default mode (exec claude)" {
  # No caam available → should exec claude with the args
  unset CCPOOL_MOCK_CAAM_PROFILES
  rm -f "${FIXTURES_BIN}/caam.disabled" 2>/dev/null
  # Hide caam from PATH so default-mode does the no-caam fall-through
  export PATH="/usr/bin:/bin"
  # claude mock prints its version
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CCPOOL}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
}

@test "ccpool with no args, no caam, falls through to default mode" {
  export PATH="/usr/bin:/bin"
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CCPOOL}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
}
