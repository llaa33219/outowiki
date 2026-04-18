"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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
