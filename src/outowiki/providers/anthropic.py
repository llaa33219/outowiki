"""Anthropic Claude LLM provider."""

import json
from typing import TypeVar

from anthropic import APIConnectionError, APIStatusError, Anthropic, RateLimitError
from pydantic import BaseModel

from ..core.exceptions import ProviderError
from .base import LLMProvider

T = TypeVar("T", bound=BaseModel)


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4000,
        **kwargs: object,
    ):
        self.client = Anthropic(
            api_key=api_key,
            base_url=base_url if base_url != "https://api.anthropic.com" else None,
            max_retries=2,
        )
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, prompt: str, **kwargs: object) -> str:
        try:
            response = self.client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                messages=[{"role": "user", "content": prompt}],
            )
            return str(response.content[0].text)
        except APIConnectionError as e:
            raise ProviderError(f"Connection error: {e}") from e
        except RateLimitError as e:
            raise ProviderError(f"Rate limit exceeded: {e}") from e
        except APIStatusError as e:
            raise ProviderError(f"API error {e.status_code}") from e

    def complete_with_schema(
        self,
        prompt: str,
        schema: type[T],
        **kwargs: object,
    ) -> T:
        schema_prompt = (
            f"{prompt}\n\nRespond with valid JSON matching this schema:\n"
            f"{schema.model_json_schema()}"
        )
        response_text = self.complete(schema_prompt, **kwargs)
        try:
            data = json.loads(response_text)
            return schema.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            raise ProviderError(f"Failed to parse schema: {e}") from e

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
