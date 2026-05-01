# Shell prompt integrations

`ccpool statusline` emits a one-line JSON snapshot of the current profile, utilization, and saturation/degraded flags — designed for shell prompt frameworks. `ccpool statusline --short` emits a single-line text rendering (emoji + profile + percentages) suitable for direct interpolation.

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
[custom.ccpool]
command = "ccpool statusline --short"
when = "command -v ccpool"
format = "[$output]($style) "
style = "bold cyan"
shell = ["bash", "--noprofile", "--norc"]
```

The `--short` mode emits something like `🟢 personal 42% / 71%`, which fits cleanly inside a single prompt segment. Starship caches the output between renders; if you want a livelier signal, drop `cache_seconds = 30` into the block.

## Powerlevel10k (zsh)

Add a custom segment in `~/.p10k.zsh`:

```zsh
function prompt_ccpool() {
  if (( ${+commands[ccpool]} )); then
    local out
    out="$(ccpool statusline --short 2>/dev/null)" || return
    p10k segment -f cyan -t "${out}"
  fi
}

# Then add `ccpool` to your POWERLEVEL9K_LEFT_PROMPT_ELEMENTS or
# POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS array.
```

## oh-my-zsh

In a custom theme (`~/.oh-my-zsh/custom/themes/<your>.zsh-theme`):

```zsh
function ccpool_prompt_info() {
  if command -v ccpool >/dev/null 2>&1; then
    ccpool statusline --short 2>/dev/null
  fi
}

PROMPT='%{$fg_bold[blue]%}%n@%m%{$reset_color%} $(ccpool_prompt_info) %{$fg[cyan]%}%~%{$reset_color%}\$ '
```

## tmux status line

Add to `~/.tmux.conf`:

```tmux
set -g status-right '#(ccpool statusline --short) | %H:%M'
set -g status-interval 30
```

The interval matches Anthropic's 5-minute usage cache window — polling more often won't yield fresher data.

## Plain bash PROMPT_COMMAND

For a no-framework setup:

```bash
PROMPT_COMMAND='__ccpool="$(ccpool statusline --short 2>/dev/null)"; '$PROMPT_COMMAND
PS1='$__ccpool \w \$ '
```

## Programmatic consumers (jq pipelines)

Pull specific fields:

```bash
# Active profile + 5h utilization
ccpool statusline | jq -r '"\(.profile) \(.five_hour_pct)%"'

# Alert if saturated
if [[ "$(ccpool statusline | jq -r '.saturated')" == "true" ]]; then
  notify-send "ccpool saturated"
fi
```

When the usage endpoint is unreachable, `five_hour_pct` and `seven_day_pct` are `null`. Always guard your jq pipeline with `// "n/a"` (or similar) when interpolating those fields into a string.

## Integration testing

Bats coverage in `tests/integration/test_status_render.bats` and `tests/e2e/test_first_run.bats` asserts the JSON keys above. If you add a new prompt-framework example, please add a smoke test that does the JSON parse with stdlib python.
