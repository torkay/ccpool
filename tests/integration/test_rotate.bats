#!/usr/bin/env bats
# `cmax rotate` token replacement.
#
# `cmax rotate` is interactive (prompts for paste). We test the surface that
# is mechanically observable without TTY: the secrets backend round-trip via
# the python CLI directly. The full bash rotate flow is covered by the
# `_issue_token_for` interactive path which requires a TTY and is outside
# bats' reach.

load 'test_helper'

setup() {
  cmax_setup_env
  cmax_seed_config
}

teardown() {
  cmax_teardown_env
}

@test "secrets round-trip writes and reads via env backend" {
  python3 -c "
from cmaxctl import secrets
backend, err = secrets.set_token('alpha', 'sk-ant-oat01-rotated', 'tester+alpha@example.com')
assert backend == 'env', f'expected env, got {backend}: {err}'
tok = secrets.get_token('alpha')
assert tok == 'sk-ant-oat01-rotated', f'wrong token: {tok}'
"
}

@test "secrets delete_token removes from env backend" {
  python3 -c "
from cmaxctl import secrets
secrets.set_token('alpha', 'sk-ant-oat01-rot1', 'a@b.co')
removed = secrets.delete_token('alpha')
assert removed, 'delete returned False'
tok = secrets.get_token('alpha')
assert tok is None, f'token still present: {tok}'
"
}

@test "record-token writes age tracking under tokens.json" {
  # `record-token` is a python-CLI-only helper (used by setup/_issue_token_for).
  cmax_seed_token alpha
  run python3 -m cmaxctl.cli record-token alpha tester+alpha@example.com
  [ "${status}" -eq 0 ]
  [ -f "${XDG_DATA_HOME}/cmaxctl/tokens.json" ]
  python3 -c "
import json
d = json.loads(open('${XDG_DATA_HOME}/cmaxctl/tokens.json').read())
assert 'alpha' in d, f'alpha missing from {list(d.keys())}'
assert d['alpha']['account'] == 'tester+alpha@example.com'
"
}

@test "rotate target=all enumerates configured profiles (dry-probe)" {
  # We can't run full rotate (interactive); we can confirm the python
  # iteration over cfg.profiles works without erroring.
  python3 -c "
from cmaxctl import config
cfg = config.load()
assert len(cfg.profiles) == 2, f'expected 2, got {len(cfg.profiles)}'
assert {p.name for p in cfg.profiles} == {'alpha','beta'}
"
}
