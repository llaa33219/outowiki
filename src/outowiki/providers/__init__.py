"""LLM provider integrations for OpenAI and Anthropic APIs."""

from typing import Any

from .base import LLMProvider

# Lazy imports to handle missing dependencies
def __getattr__(name: str) -> Any:
    if name == "OpenAIProvider":
        try:
            from .openai import OpenAIProvider
            return OpenAIProvider
        except ImportError:
            raise ImportError(
                "OpenAIProvider requires the 'openai' package. "
                "Install it with: pip install openai"
            )
    elif name == "AnthropicProvider":
        try:
            from .anthropic import AnthropicProvider
            return AnthropicProvider
        except ImportError:
            raise ImportError(
                "AnthropicProvider requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
]
