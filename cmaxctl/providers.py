"""cmaxctl/providers.py — provider strategy table.

caam itself supports `claude`, `codex`, and `gemini`. cmaxctl v1.0 wires up
**claude full + codex/gemini stubs**. The stubs surface a clean
`NotImplementedError` with a tracking-issue pointer when an operator tries
to set `provider.name = "codex"` (or `"gemini"`) before the strategy is
implemented — rather than producing weird half-broken behaviour.

Per ADR-0008 + plan §8: each provider has a strategy with login command
template, token issuance command, usage endpoint URL, and a flag for
whether the upstream exposes a usage API at all.

Stdlib only.
"""
from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_PROVIDERS = ("claude", "codex", "gemini")
IMPLEMENTED_PROVIDERS = ("claude",)


class UnsupportedProviderError(NotImplementedError):
    """Raised when a recognised-but-not-yet-implemented provider is invoked.

    Subclass of NotImplementedError so callers don't have to import this
    type to catch it generically.
    """


@dataclass(frozen=True)
class ProviderStrategy:
    """Per-provider command + endpoint table.

    `login_cmd_argv` and `token_issue_cmd_argv` are argv lists with `{email}`
    placeholders; callers substitute and exec.

    `usage_endpoint` is None when upstream doesn't expose a usage API — in
    that case the picker drops back to caam-smart + round-robin tiers only.
    """
    name: str
    binary: str  # default binary name on $PATH
    login_cmd_argv: tuple[str, ...]
    token_issue_cmd_argv: tuple[str, ...]
    usage_endpoint: str | None
    supports_usage_api: bool
    # Identity-marker strategy: what stable account-level value we hash
    # to detect "same-account on two profiles". Today this is claude-specific.
    has_identity_marker: bool


CLAUDE = ProviderStrategy(
    name="claude",
    binary="claude",
    login_cmd_argv=("claude", "auth", "login", "--claudeai", "--email", "{email}"),
    token_issue_cmd_argv=("claude", "setup-token"),
    usage_endpoint="https://api.anthropic.com/api/oauth/usage",
    supports_usage_api=True,
    has_identity_marker=True,
)


def get_strategy(provider_name: str) -> ProviderStrategy:
    """Return the strategy for `provider_name` or raise.

    UnsupportedProviderError fires for codex/gemini (recognised, not yet built).
    ValueError fires for completely unknown names.
    """
    if not provider_name:
        raise ValueError("provider name is empty")
    name = provider_name.strip().lower()
    if name == "claude":
        return CLAUDE
    if name == "codex":
        raise UnsupportedProviderError(
            "provider 'codex' is recognised by caam but not yet implemented in "
            "cmaxctl 1.0. Tracking: https://github.com/torkay/cmaxctl/issues "
            "(filter by label:provider). Switch [provider] name = \"claude\" "
            "in your config.toml to continue."
        )
    if name == "gemini":
        raise UnsupportedProviderError(
            "provider 'gemini' is recognised by caam but not yet implemented in "
            "cmaxctl 1.0. Tracking: https://github.com/torkay/cmaxctl/issues "
            "(filter by label:provider). Switch [provider] name = \"claude\" "
            "in your config.toml to continue."
        )
    raise ValueError(
        f"unknown provider {provider_name!r}; supported: {', '.join(SUPPORTED_PROVIDERS)}"
    )


def is_implemented(provider_name: str) -> bool:
    """Cheap predicate for doctor checks. Doesn't raise."""
    return (provider_name or "").strip().lower() in IMPLEMENTED_PROVIDERS
