#!/usr/bin/env bats
# `ccpool status` renders profile names + token state from a seeded config.
#
# Status reaches into config.toml, the caam profiles dir, and the secrets
# backend. With env-only secrets and pre-seeded caam profiles, it should
# produce a structured snapshot.

load 'test_helper'

setup() {
  ccpool_setup_env
  ccpool_seed_config myowner
  ccpool_seed_caam_profile alpha
  ccpool_seed_caam_profile beta
  ccpool_seed_token alpha
  ccpool_seed_token beta
}

teardown() {
  ccpool_teardown_env
}

@test "ccpool status mentions both profile names" {
  run "${CCPOOL}" status
  [[ "${output}" == *"alpha"* ]]
  [[ "${output}" == *"beta"* ]]
}

@test "ccpool status --json emits structured JSON with profile data" {
  run "${CCPOOL}" status --json
  python3 -c "
import json
d = json.loads('''${output}''')
assert isinstance(d, dict), 'top-level not dict'
# Some shape is expected — accept either 'profiles' (top-level) or nested
hit = ('profiles' in d) or any('profiles' in (v if isinstance(v, dict) else {}) for v in d.values())
assert hit, f'no profiles key found: {list(d.keys())}'
"
}

@test "python cli inventory reflects seeded credentials" {
  # `inventory` is a python-CLI-only command (called by bin/ccpool setup
  # internally, not exposed as a top-level subcommand). Test direct.
  run python3 -m ccpool.cli inventory
  [ "${status}" -eq 0 ]
  python3 -c "
import json
d = json.loads('''${output}''')
profiles = d.get('profiles', {})
assert 'alpha' in profiles, f'alpha missing from {list(profiles.keys())}'
assert profiles['alpha'].get('credentials_present') is True, 'alpha creds not detected'
"
}

@test "ccpool statusline reads profile from config" {
  run "${CCPOOL}" statusline
  [ "${status}" -eq 0 ]
  python3 -c "
import json
d = json.loads('''${output}''')
# Without live usage data, profile may be the first seeded or empty — either OK
# but the JSON must validate.
assert d.get('version') == 1
assert isinstance(d.get('saturated'), bool)
"
}

@test "ccpool usage --json runs against mocked caam (no live network)" {
  run "${CCPOOL}" usage --json
  # Usage reaches Anthropic /api/oauth/usage; without a server it'll degrade.
  # We only assert clean JSON output (no traceback).
  python3 -c "
import json
try:
    d = json.loads('''${output}''')
    assert isinstance(d, (dict, list))
except json.JSONDecodeError:
    # Empty / non-JSON is acceptable when offline; just ensure no traceback
    assert 'Traceback' not in '''${output}''', 'traceback in output'
"
}
