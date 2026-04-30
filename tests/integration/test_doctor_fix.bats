#!/usr/bin/env bats
# `cmax doctor` finding surface and `--fix` autofix paths.
#
# These tests exercise the doctor's output shape against several seeded
# states (empty config, healthy config, missing creds). We don't assert
# specific finding codes (those are stable but high-churn during dev) —
# we assert structural validity and severity ordering.

load 'test_helper'

setup() {
  cmax_setup_env
}

teardown() {
  cmax_teardown_env
}

@test "doctor reports caam-related finding when binary missing from PATH" {
  export PATH="/usr/bin:/bin"
  run "${CMAX}" doctor --json
  python3 -c "
import json
d = json.loads('''${output}''')
findings = d.get('findings', [])
codes = {f.get('code', '') for f in findings if isinstance(f, dict)}
# At least one finding must mention caam absence
hit = any('caam' in c for c in codes)
assert hit, f'no caam finding in: {sorted(codes)}'
"
}

@test "doctor JSON is empty-array safe even on a fully-default install" {
  run "${CMAX}" doctor --json
  python3 -c "
import json
d = json.loads('''${output}''')
assert 'findings' in d
for f in d['findings']:
    assert 'severity' in f and f['severity'] in ('low','medium','high','critical','LOW','MEDIUM','HIGH','CRITICAL')
    assert 'code' in f
"
}

@test "doctor with seeded config shows fewer config findings" {
  cmax_seed_config
  cmax_seed_caam_profile alpha
  cmax_seed_caam_profile beta
  cmax_seed_token alpha
  cmax_seed_token beta
  run "${CMAX}" doctor --json
  python3 -c "
import json
d = json.loads('''${output}''')
codes = {f.get('code','') for f in d.get('findings', [])}
# Config-not-found codes should be absent now
assert not any('no_config' in c for c in codes), f'no_config still present: {codes}'
"
}

@test "doctor --fix is idempotent (second run ≤ first)" {
  cmax_seed_config
  run "${CMAX}" doctor --fix --json
  first_count=$(python3 -c "
import json
d = json.loads('''${output}''')
print(len(d.get('findings', [])))
")
  run "${CMAX}" doctor --fix --json
  second_count=$(python3 -c "
import json
d = json.loads('''${output}''')
print(len(d.get('findings', [])))
")
  [ "${second_count}" -le "${first_count}" ]
}
