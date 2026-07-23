import logging

from django.conf import settings

from .claude import ClaudeProvider
from .extractive import ExtractiveProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from .smollm import SmolLMProvider

logger = logging.getLogger(__name__)

# Providers register themselves here as they're added (9.2-9.4: claude,
# openai, ollama; smollm added later - runs a small model in-process via
# transformers, no separate runtime/server needed). Each entry is a
# zero-arg factory so unavailable SDKs for unused providers never get
# imported (the SDK import itself lives inside each provider's __init__,
# not at module level).
_REGISTRY = {
    "extractive": ExtractiveProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "smollm": SmolLMProvider,
}

# Settings a provider needs before it's safe to instantiate. Providers
# not listed here (e.g. ollama - no API key, just a reachable server)
# are instantiated directly; their own __init__/generate is responsible
# for failing clearly if unreachable.
_REQUIRED_SETTING = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def register_provider(name, factory):
    _REGISTRY[name] = factory


def get_provider():
    """Return the configured LLMProvider. Falls back to ExtractiveProvider
    - loudly logged, never a silent swap - when LLM_PROVIDER is unset or
    names a provider that isn't registered (e.g. its SDK/API key isn't
    configured yet).
    """
    name = (settings.LLM_PROVIDER or "").strip().lower()

    if not name:
        logger.info("LLM_PROVIDER not set; using ExtractiveProvider (no-LLM answer mode).")
        return ExtractiveProvider()

    factory = _REGISTRY.get(name)
    if factory is None:
        logger.warning(
            "LLM_PROVIDER=%r is not a registered provider; falling back to ExtractiveProvider.",
            name,
        )
        return ExtractiveProvider()

    required_setting = _REQUIRED_SETTING.get(name)
    if required_setting and not getattr(settings, required_setting, ""):
        logger.warning(
            "LLM_PROVIDER=%r requires settings.%s, which is not set; falling back to "
            "ExtractiveProvider.",
            name,
            required_setting,
        )
        return ExtractiveProvider()

    return factory()
