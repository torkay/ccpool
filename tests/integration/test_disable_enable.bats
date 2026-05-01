#!/usr/bin/env bats
# Master kill-switch round-trip: disable creates a flag, default mode skips
# rotation entirely (raw exec of claude); enable removes the flag.
#
# Per plan §12.2 + ADR-0004 (no-resident-daemon): kill-switch is a sentinel
# file under $XDG_DATA_HOME/ccpool/disabled. No process state.

load 'test_helper'

setup() {
  ccpool_setup_env
}

teardown() {
  ccpool_teardown_env
}

@test "ccpool disable creates the disabled sentinel" {
  run "${CCPOOL}" disable
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"disabled"* ]]
  [ -f "${XDG_DATA_HOME}/ccpool/disabled" ]
}

@test "ccpool disable then enable round-trip" {
  "${CCPOOL}" disable
  [ -f "${XDG_DATA_HOME}/ccpool/disabled" ]
  run "${CCPOOL}" enable
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"enabled"* ]]
  [ ! -f "${XDG_DATA_HOME}/ccpool/disabled" ]
}

@test "ccpool enable when not disabled is idempotent" {
  run "${CCPOOL}" enable
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"enabled"* ]]
}

@test "default mode under disabled flag execs claude unwrapped" {
  "${CCPOOL}" disable
  # With disabled flag set, no caam invocation should happen — even though
  # CCPOOL_MOCK_CAAM_PROFILES seeds 2 profiles, the flag should short-circuit.
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CCPOOL}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
}

@test "CLAUDE_ROTATE_DISABLE=1 acts as transient kill-switch" {
  CLAUDE_ROTATE_DISABLE=1 \
    CLAUDE_BIN="${FIXTURES_BIN}/claude" \
    run "${CCPOOL}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
  # Real on-disk flag was never written
  [ ! -f "${XDG_DATA_HOME}/ccpool/disabled" ]
}
