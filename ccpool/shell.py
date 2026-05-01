"""ccpool/shell.py — managed shell-rc block writer.

Writes (or removes) a marked block to ~/.zshrc / ~/.bashrc / fish conf.d.
Only writes the block to files that already exist (we don't create them).
Always preserves user content outside the markers.

Markers:
    # >>> ccpool managed block — do not edit by hand
    ...
    # <<< ccpool

The block contents depend on cfg.shell:
  alias_claude  → `alias claude='ccpool'`
  export_flags  → exports for AGENT_FLEET_USE_CAAM*, CLAUDE_ROTATE_USE_TOKEN, etc.
"""
from __future__ import annotations

import os
from pathlib import Path

from ccpool import config, paths

BEGIN_MARKER = "# >>> ccpool managed block — do not edit by hand"
END_MARKER = "# <<< ccpool"
LEGACY_BEGIN_MARKERS = ["# >>> ccpool (Claude Max rotation) — managed block, do not edit by hand"]
LEGACY_END_MARKERS = ["# <<< ccpool"]


def _block_text(cfg: config.Config) -> str:
    lines = [BEGIN_MARKER]
    if cfg.shell.alias_claude:
        lines.append("alias claude='ccpool'")
    if cfg.shell.export_flags:
        lines.extend([
            "export CCPOOL_USE_TOKEN=1",
            "export AGENT_FLEET_USE_CAAM=1",
            "export AGENT_FLEET_USE_CAAM_TOKEN=1",
            "export CLAUDE_ROTATE_USE_TOKEN=1",
        ])
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def _file_has_block(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        return BEGIN_MARKER in path.read_text()
    except OSError:
        return False


def _candidate_files(cfg: config.Config) -> list[Path]:
    """Files we write to. Both: cfg.shell.files AND any default candidates that exist."""
    out: list[Path] = []
    seen: set[str] = set()
    for raw in cfg.shell.files:
        p = Path(os.path.expanduser(raw))
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    for p in paths.candidate_shell_rc_files():
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def install(cfg: config.Config | None = None) -> list[tuple[Path, str]]:
    """Write the managed block to existing rc files. Returns [(path, action)] log.

    action ∈ {"installed", "updated", "skipped:no-file", "fish-created"}.
    """
    if cfg is None:
        cfg = config.load()
    if not cfg.shell.manage_rc_file:
        return []

    block = _block_text(cfg)
    log: list[tuple[Path, str]] = []

    for path in _candidate_files(cfg):
        is_fish = path.suffix == ".fish" or "fish" in str(path)
        if is_fish:
            # Fish conf.d files: we DO create the dir + file (it's standalone)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                fish_block = block.replace("alias claude='ccpool'", "alias claude 'ccpool'")
                fish_block = fish_block.replace("export ", "set -gx ")
                fish_block = fish_block.replace(" =1", " 1")
                path.write_text(fish_block)
                log.append((path, "fish-created"))
            except OSError:
                pass
            continue
        if not path.exists():
            log.append((path, "skipped:no-file"))
            continue
        try:
            existing = path.read_text()
        except OSError:
            continue
        if BEGIN_MARKER in existing:
            # Update in place
            new = _replace_block(existing, block)
            try:
                path.write_text(new)
                log.append((path, "updated"))
            except OSError:
                pass
        else:
            new = _strip_legacy_blocks(existing) + ("" if existing.endswith("\n") else "\n") + block
            try:
                path.write_text(new)
                log.append((path, "installed"))
            except OSError:
                pass

    return log


def remove(cfg: config.Config | None = None) -> list[Path]:
    """Strip the managed block from all rc files. Returns the list of files modified."""
    if cfg is None:
        cfg = config.load()
    modified: list[Path] = []
    for path in _candidate_files(cfg):
        if not path.exists():
            continue
        try:
            existing = path.read_text()
        except OSError:
            continue
        if BEGIN_MARKER not in existing and not _has_legacy_block(existing):
            continue
        new = _strip_block(existing)
        new = _strip_legacy_blocks(new)
        try:
            path.write_text(new)
            modified.append(path)
        except OSError:
            pass
    return modified


def _replace_block(existing: str, replacement: str) -> str:
    out_lines: list[str] = []
    skip = False
    for line in existing.splitlines(keepends=True):
        if line.strip() == BEGIN_MARKER:
            skip = True
            continue
        if skip and line.strip() == END_MARKER:
            skip = False
            out_lines.append(replacement)
            continue
        if not skip:
            out_lines.append(line)
    return "".join(out_lines)


def _strip_block(existing: str) -> str:
    out_lines: list[str] = []
    skip = False
    for line in existing.splitlines(keepends=True):
        if line.strip() == BEGIN_MARKER:
            skip = True
            continue
        if skip and line.strip() == END_MARKER:
            skip = False
            continue
        if not skip:
            out_lines.append(line)
    return "".join(out_lines)


def _has_legacy_block(text: str) -> bool:
    return any(m in text for m in LEGACY_BEGIN_MARKERS)


def _strip_legacy_blocks(text: str) -> str:
    """Remove old `ccpool (Claude Max rotation)` blocks from v0 setups."""
    for begin in LEGACY_BEGIN_MARKERS:
        if begin not in text:
            continue
        out_lines: list[str] = []
        skip = False
        for line in text.splitlines(keepends=True):
            if line.startswith(begin):
                skip = True
                continue
            if skip and any(end in line for end in LEGACY_END_MARKERS):
                skip = False
                continue
            if not skip:
                out_lines.append(line)
        text = "".join(out_lines)
    return text
