"""Unit tests for cmaxctl.providers — strategy table + stub error shape."""
from __future__ import annotations

import pytest

from cmaxctl import providers


def test_claude_strategy_complete():
    s = providers.get_strategy("claude")
    assert s.name == "claude"
    assert s.binary == "claude"
    assert s.usage_endpoint and "anthropic.com" in s.usage_endpoint
    assert s.supports_usage_api is True
    assert s.has_identity_marker is True
    assert "{email}" in s.login_cmd_argv


def test_claude_case_insensitive():
    assert providers.get_strategy("CLAUDE").name == "claude"
    assert providers.get_strategy("Claude").name == "claude"
    assert providers.get_strategy("  claude  ").name == "claude"


@pytest.mark.parametrize("provider", ["codex", "gemini"])
def test_recognised_but_not_implemented_raises_unsupported(provider):
    with pytest.raises(providers.UnsupportedProviderError) as exc:
        providers.get_strategy(provider)
    msg = str(exc.value)
    assert provider in msg
    assert "not yet implemented" in msg
    assert "config.toml" in msg  # remediation hint must appear


def test_unsupported_is_subclass_of_not_implemented_error():
    """Callers can catch with stdlib NotImplementedError without importing us."""
    with pytest.raises(NotImplementedError):
        providers.get_strategy("codex")


@pytest.mark.parametrize("name", ["", "  ", None])
def test_empty_provider_raises_value_error(name):
    with pytest.raises((ValueError, AttributeError)):
        providers.get_strategy(name)


def test_unknown_provider_raises_value_error():
    with pytest.raises(ValueError) as exc:
        providers.get_strategy("openai")
    assert "openai" in str(exc.value)
    assert "supported" in str(exc.value).lower()


def test_is_implemented_predicate_does_not_raise():
    assert providers.is_implemented("claude") is True
    assert providers.is_implemented("codex") is False
    assert providers.is_implemented("gemini") is False
    assert providers.is_implemented("openai") is False
    assert providers.is_implemented("") is False
    assert providers.is_implemented(None) is False


def test_supported_providers_constant():
    """Sanity: SUPPORTED reflects what caam itself supports."""
    assert "claude" in providers.SUPPORTED_PROVIDERS
    assert "codex" in providers.SUPPORTED_PROVIDERS
    assert "gemini" in providers.SUPPORTED_PROVIDERS
    # IMPLEMENTED is a strict subset
    assert set(providers.IMPLEMENTED_PROVIDERS) <= set(providers.SUPPORTED_PROVIDERS)
