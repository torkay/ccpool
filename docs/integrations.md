# Shell prompt integrations

`cmax statusline` emits a one-line JSON snapshot of the current profile, utilization, and saturation/degraded flags — designed for shell prompt frameworks. `cmax statusline --short` emits a single-line text rendering (emoji + profile + percentages) suitable for direct interpolation.

## JSON shape

```json
{
  "version": 1,
  "profile": "personal",
  "five_hour_pct": 42.0,
  "seven_day_pct": 71.5,
  "saturated": false,
  "degraded": false,
  "emoji": "🟢"
}
```

| Key | Type | Notes |
|---|---|---|
| `version` | int | Bumped on incompatible JSON changes; integrations should pin |
| `profile` | string | Active profile name; empty string when no live data |
| `five_hour_pct` | float·null | `null` when usage endpoint is unreachable |
| `seven_day_pct` | float·null | `null` when usage endpoint is unreachable |
| `saturated` | bool | `true` when all profiles are above `picker.hard_threshold_pct` |
| `degraded` | bool | `true` when usage endpoint is in fallback mode |
| `emoji` | string | 🟢 healthy · 🟡 ≥ soft threshold · 🔴 saturated · ⚪ degraded |

## Starship

[Starship](https://starship.rs/) renders prompt segments via `[custom]` blocks. Add to `~/.config/starship.toml`:

```toml
[custom.cmax]
command = "cmax statusline --short"
when = "command -v cmax"
format = "[$output]($style) "
style = "bold cyan"
shell = ["bash", "--noprofile", "--norc"]
```

The `--short` mode emits something like `🟢 personal 42% / 71%`, which fits cleanly inside a single prompt segment. Starship caches the output between renders; if you want a livelier signal, drop `cache_seconds = 30` into the block.

## Powerlevel10k (zsh)

Add a custom segment in `~/.p10k.zsh`:

```zsh
function prompt_cmax() {
  if (( ${+commands[cmax]} )); then
    local out
    out="$(cmax statusline --short 2>/dev/null)" || return
    p10k segment -f cyan -t "${out}"
  fi
}

# Then add `cmax` to your POWERLEVEL9K_LEFT_PROMPT_ELEMENTS or
# POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS array.
```

## oh-my-zsh

In a custom theme (`~/.oh-my-zsh/custom/themes/<your>.zsh-theme`):

```zsh
function cmax_prompt_info() {
  if command -v cmax >/dev/null 2>&1; then
    cmax statusline --short 2>/dev/null
  fi
}

PROMPT='%{$fg_bold[blue]%}%n@%m%{$reset_color%} $(cmax_prompt_info) %{$fg[cyan]%}%~%{$reset_color%}\$ '
```

## tmux status line

Add to `~/.tmux.conf`:

```tmux
set -g status-right '#(cmax statusline --short) | %H:%M'
set -g status-interval 30
```

The interval matches Anthropic's 5-minute usage cache window — polling more often won't yield fresher data.

## Plain bash PROMPT_COMMAND

For a no-framework setup:

```bash
PROMPT_COMMAND='__cmax="$(cmax statusline --short 2>/dev/null)"; '$PROMPT_COMMAND
PS1='$__cmax \w \$ '
```

## Programmatic consumers (jq pipelines)

Pull specific fields:

```bash
# Active profile + 5h utilization
cmax statusline | jq -r '"\(.profile) \(.five_hour_pct)%"'

# Alert if saturated
if [[ "$(cmax statusline | jq -r '.saturated')" == "true" ]]; then
  notify-send "cmax saturated"
fi
```

When the usage endpoint is unreachable, `five_hour_pct` and `seven_day_pct` are `null`. Always guard your jq pipeline with `// "n/a"` (or similar) when interpolating those fields into a string.

## Integration testing

Bats coverage in `tests/integration/test_status_render.bats` and `tests/e2e/test_first_run.bats` asserts the JSON keys above. If you add a new prompt-framework example, please add a smoke test that does the JSON parse with stdlib python.
