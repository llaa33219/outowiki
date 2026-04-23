"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class ToolCall:
    """Represents a tool call from the LLM."""
    id: str
    name: str
    arguments: str
    parsed_arguments: dict[str, Any] | None = None


@dataclass
class ProviderResponse:
    """Unified response from LLM provider."""
    content: str | None
    tool_calls: list[ToolCall] | None
    finish_reason: str


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str, **kwargs: object) -> str:
        """Get completion from LLM.

        Args:
            prompt: The prompt to send
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            The completion text

        Raises:
            ProviderError: If the request fails
        """
        pass

    @abstractmethod
    def complete_with_schema(
        self,
        prompt: str,
        schema: type[T],
        **kwargs: object,
    ) -> T:
        """Get structured completion matching a Pydantic schema.

        Args:
            prompt: The prompt to send
            schema: Pydantic model class for response validation
            **kwargs: Additional parameters

        Returns:
            Instance of the schema with parsed response

        Raises:
            ProviderError: If the request fails
            ValidationError: If response doesn't match schema
        """
        pass

    @abstractmethod
    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: object,
    ) -> ProviderResponse:
        """Multi-turn tool-calling completion.

        Args:
            messages: Conversation history
            tools: Tool definitions for the LLM
            **kwargs: Additional parameters

        Returns:
            ProviderResponse with content and/or tool calls

        Raises:
            ProviderError: If the request fails
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name/identifier."""
        pass

    @property
    @abstractmethod
    def max_tokens(self) -> int:
        """Return the maximum token limit."""
        pass
