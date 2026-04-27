"""cmaxctl/notify.py — optional notify-hook abstraction.

Replaces the personal-substrate `notify_dispatch.py` Telegram dependency.
The hook is platform-neutral: a list-form command (no shell interpolation)
that receives a JSON payload on stdin.

Configured via `cfg.notify.command` (list of args) and `cfg.notify.severities`
(filter). Empty `command` = no-op.

Stdlib only.
"""
from __future__ import annotations

import json
import subprocess
from typing import Any

from cmaxctl import config


def fire(severity: str, title: str, message: str,
         type_: str = "cmaxctl",
         extra: dict[str, Any] | None = None,
         cfg: config.Config | None = None) -> bool:
    """Best-effort notification. Returns True if a notify command was invoked."""
    if cfg is None:
        cfg = config.load()

    if not cfg.notify.command:
        return False
    if cfg.notify.severities and severity not in cfg.notify.severities:
        return False

    payload = {
        "severity": severity,
        "title": title,
        "message": message,
        "type": type_,
    }
    if extra:
        payload.update(extra)

    try:
        # Hard rule: cfg.notify.command is a list, not a string. No shell=True.
        # Substitution: the command receives JSON on stdin; templating is
        # the receiver's responsibility (not ours).
        subprocess.run(
            cfg.notify.command,
            input=json.dumps(payload),
            text=True,
            timeout=10,
            capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def fire_simple(severity: str, message: str,
                cfg: config.Config | None = None) -> bool:
    """Convenience wrapper for ad-hoc notifications."""
    return fire(severity=severity, title="cmaxctl", message=message, cfg=cfg)
