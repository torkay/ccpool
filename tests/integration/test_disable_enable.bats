#!/usr/bin/env bats
# Master kill-switch round-trip: disable creates a flag, default mode skips
# rotation entirely (raw exec of claude); enable removes the flag.
#
# Per plan §12.2 + ADR-0004 (no-resident-daemon): kill-switch is a sentinel
# file under $XDG_DATA_HOME/cmaxctl/disabled. No process state.

load 'test_helper'

setup() {
  cmax_setup_env
}

teardown() {
  cmax_teardown_env
}

@test "cmax disable creates the disabled sentinel" {
  run "${CMAX}" disable
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"disabled"* ]]
  [ -f "${XDG_DATA_HOME}/cmaxctl/disabled" ]
}

@test "cmax disable then enable round-trip" {
  "${CMAX}" disable
  [ -f "${XDG_DATA_HOME}/cmaxctl/disabled" ]
  run "${CMAX}" enable
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"enabled"* ]]
  [ ! -f "${XDG_DATA_HOME}/cmaxctl/disabled" ]
}

@test "cmax enable when not disabled is idempotent" {
  run "${CMAX}" enable
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"enabled"* ]]
}

@test "default mode under disabled flag execs claude unwrapped" {
  "${CMAX}" disable
  # With disabled flag set, no caam invocation should happen — even though
  # CMAX_MOCK_CAAM_PROFILES seeds 2 profiles, the flag should short-circuit.
  CLAUDE_BIN="${FIXTURES_BIN}/claude" run "${CMAX}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
}

@test "CLAUDE_ROTATE_DISABLE=1 acts as transient kill-switch" {
  CLAUDE_ROTATE_DISABLE=1 \
    CLAUDE_BIN="${FIXTURES_BIN}/claude" \
    run "${CMAX}" --version
  [ "${status}" -eq 0 ]
  [[ "${output}" == *"Claude Code"* ]]
  # Real on-disk flag was never written
  [ ! -f "${XDG_DATA_HOME}/cmaxctl/disabled" ]
}
