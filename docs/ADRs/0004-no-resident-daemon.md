# ADR-0004 — No resident daemon process

Date: 2026-04-27 · Status: accepted

## Context

Account rotation could be implemented as a long-running daemon that holds OAuth state in memory, polls the usage endpoint on a schedule, and signals child `claude` processes to migrate. That gets complex fast: process supervision, crash recovery, IPC, log-rotation, restart-on-config-change, etc.

The personal substrate this evolved from instead uses a launchd interval job that runs a 50ms Python script every 5 minutes — pure tick semantics, no persistent state in memory.

## Decision

cmaxctl has **no resident daemon process**.

- Rotation watcher = launchd `StartInterval` job (macOS) / systemd-user `OnUnitInactiveSec` timer (Linux) / crontab fallback. Each fire executes a Python module, exits, leaves no resident process.
- Daily watchdog = same model, fires once per day.
- Picker (`cmax pick`) is invoked synchronously by the bash dispatcher; no IPC.

## Why

| Property | Daemon | Tick model |
|---|---|---|
| Crash recovery | needs supervisor (launchd Keep-Alive etc) | irrelevant — next tick recovers automatically |
| State persistence | in-memory + flush | filesystem from the start |
| Resource use | always-on | <50ms per tick |
| Debugging | logs from a long-lived process | newline-delimited JSON to `watcher.ndjson` |
| Config changes | needs SIGHUP / restart | next tick reads current config |
| Unprivileged install | needs user-mode daemon support | works on any system with launchd / systemd-user / cron |

## Consequences

- All state goes through the filesystem (`~/.local/share/cmaxctl/`). That's also our integration contract: any tool that reads those files sees authoritative state.
- No bg-process kill/restart UX. `cmax disable` / `cmax enable` toggles a flag file; next tick honours it.
- Inter-tick state (e.g. "I just rotated, anti-flap for 10 minutes") goes through `watcher.last_rotate` mtime — no inter-process coordination needed.

## Out of scope

If a real-time rotation requirement emerges (latency-critical fleets), that would need a daemon and a new ADR.
