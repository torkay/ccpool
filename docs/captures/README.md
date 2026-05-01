# Terminal captures

Animated `.gif` recordings of `ccpool` for the README and docs. Generated with [VHS](https://github.com/charmbracelet/vhs), which takes plain text `.tape` files and emits gif/png/mp4.

The recordings are deterministic. They run against a small shim at `_demo-env/ccpool` that mimics the real CLI with canned output, so the GIFs don't depend on real OAuth state or real account data.

## Prerequisites

```bash
# macOS
brew install vhs ttyd ffmpeg

# Linux (vhs releases include a static binary)
# https://github.com/charmbracelet/vhs/releases
```

VHS needs `ttyd` for the headless terminal and `ffmpeg` for video encoding.

## Generating

```bash
# from repo root
vhs docs/captures/setup.tape           # writes docs/img/setup.gif
vhs docs/captures/statusline.tape      # writes docs/img/statusline.gif
vhs docs/captures/usage.tape           # writes docs/img/usage.gif
```

Each tape file uses a relative `PATH` that prepends `_demo-env/`, so it must be run from the repo root for the shim to resolve. The output GIFs land in `docs/img/` and are referenced from the top-level `README.md`.

Tapes and shim are text and version-controlled. To change what a recording shows, edit the shim's case statement (or the tape's `Type`/`Sleep` directives) and re-run vhs.

## What each tape records

- `setup.tape` — interactive `ccpool setup` walkthrough (uses a fixture `CCPOOL_HOME` so no real OAuth happens)
- `statusline.tape` — the four `ccpool statusline` modes (json, --short, --no-color, --format)
- `usage.tape` — the `ccpool usage` table with three profiles in mixed states

## Privacy guard

The shim never invokes the real `ccpool` binary; it just prints canned output. Real keychain entries, real account emails, and real usage data never appear in the recordings. The fixture profiles are named `personal`, `secondary`, `work-pro` with `you@example.com`-style placeholder addresses.
