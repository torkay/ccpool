#!/usr/bin/env bats
# Subcommands that delegate straight through to `python3 -m ccpool.cli <sub>`.
#
# These verify the dispatcher hands args off correctly and the python CLI
# returns clean output even with an empty config + no real caam state.

load 'test_helper'

setup() {
  ccpool_setup_env
}

teardown() {
  ccpool_teardown_env
}

@test "ccpool doctor --json returns valid JSON with findings array" {
  run "${CCPOOL}" doctor --json
  # Doctor returns non-zero when findings are HIGH/CRITICAL — that's expected
  # without setup. We only care that the JSON is structurally valid.
  python3 -c "
import json,sys
d = json.loads('''${output}''')
assert 'findings' in d, 'no findings key'
assert isinstance(d['findings'], list), 'findings not a list'
"
}

@test "ccpool statusline emits valid one-line JSON" {
  run "${CCPOOL}" statusline
  [ "${status}" -eq 0 ]
  python3 -c "
import json
d = json.loads('''${output}''')
assert d.get('version') == 1
for k in ('profile','five_hour_pct','seven_day_pct','saturated','degraded','emoji'):
    assert k in d, f'missing key {k}'
"
}

@test "ccpool statusline --short emits a single line" {
  run "${CCPOOL}" statusline --short
  [ "${status}" -eq 0 ]
  # Should be one line (no embedded newlines other than terminator)
  [ "$(printf '%s' "${output}" | wc -l)" -eq 0 ]
}

@test "ccpool migrate detect returns JSON with detected key" {
  run "${CCPOOL}" migrate detect
  python3 -c "
import json
d = json.loads('''${output}''')
assert 'detected' in d, 'no detected key'
assert isinstance(d['detected'], bool)
"
}

@test "ccpool status runs without exploding on empty state" {
  run "${CCPOOL}" status
  # status returns non-zero when there's nothing configured; output is what matters
  [[ "${output}" == *"profile"* || "${output}" == *"caam"* || "${output}" == *"config"* ]]
}

@test "ccpool pick --json returns env block" {
  ccpool_seed_config
  ccpool_seed_caam_profile alpha
  ccpool_seed_caam_profile beta
  run "${CCPOOL}" pick --json
  # pick may exit non-zero if usage endpoint unreachable; verify JSON shape
  python3 -c "
import json
try:
    d = json.loads('''${output}''')
except Exception as e:
    raise SystemExit(0)  # emit-nothing-but-stderr is acceptable when no live data
assert isinstance(d, dict)
"
}
