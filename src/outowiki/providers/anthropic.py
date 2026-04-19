"""Anthropic Claude LLM provider."""

from typing import Any, TypeVar

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

    def complete(self, prompt: str, **kwargs: Any) -> str:
        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                messages=[{"role": "user", "content": prompt}],
            )
            if response.content and hasattr(response.content[0], 'text'):
                return response.content[0].text or ""
            return ""
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
        **kwargs: Any,
    ) -> T:
        tools: list[dict[str, Any]] = [{
            "name": "extract",
            "description": "Extract structured data matching the schema",
            "input_schema": schema.model_json_schema()
        }]
        
        response = self.client.messages.create(
            model=self._model,
            max_tokens=kwargs.get("max_tokens", self._max_tokens),
            messages=[{"role": "user", "content": prompt}],
            tools=tools,  # type: ignore[arg-type]
        )
        
        tool_use = None
        for block in response.content:
            if block.type == "tool_use":
                tool_use = block
                break
        
        if not tool_use:
            raise ProviderError(
                "No tool call in response. The model did not return structured data."
            )
        
        try:
            return schema.model_validate(tool_use.input)
        except Exception as e:
            raise ProviderError(f"Schema validation failed: {e}") from e

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
