# VHS recording: ccpool statusline modes
# Run from repo root: vhs docs/captures/statusline.tape
# Output: docs/img/statusline.gif
Output docs/img/statusline.gif
Set FontSize 14
Set Width 1100
Set Height 460
Set Padding 18
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms

Env PATH "docs/captures/_demo-env:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"

Hide
Type "clear"
Enter
Show

Type "ccpool statusline --short"
Sleep 200ms
Enter
Sleep 800ms

Type "ccpool statusline --no-color"
Sleep 200ms
Enter
Sleep 800ms

Type `ccpool statusline --format='{marker} {profile} {five}/{seven}'`
Sleep 200ms
Enter
Sleep 1000ms

Type "ccpool statusline | jq -c '{profile, five_hour_pct, seven_day_pct}'"
Sleep 200ms
Enter
Sleep 1500ms
