"""OpenAI-compatible LLM provider."""

import json
from typing import TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    InternalServerError,
    OpenAI,
    RateLimitError,
    pydantic_function_tool,
)
from pydantic import BaseModel

from ..core.exceptions import ProviderError
from .base import LLMProvider

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
        max_tokens: int = 4000,
        **kwargs: object,
    ):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=3,
        )
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, prompt: str, **kwargs: object) -> str:
        try:
            response = self.client.chat.completions.create(  # type: ignore[call-overload]
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=kwargs.get("max_tokens", self._max_tokens),
                temperature=kwargs.get("temperature", 0.7),
            )
            return response.choices[0].message.content or ""
        except APIConnectionError as e:
            raise ProviderError(f"Connection error: {e}") from e
        except RateLimitError as e:
            raise ProviderError(f"Rate limit exceeded: {e}") from e
        except InternalServerError as e:
            raise ProviderError(f"Server error: {e}") from e
        except APIStatusError as e:
            raise ProviderError(f"API error {e.status_code}: {e.message}") from e

    def complete_with_schema(
        self,
        prompt: str,
        schema: type[T],
        **kwargs: object,
    ) -> T:
        tools = [pydantic_function_tool(schema)]
        
        response = self.client.chat.completions.parse(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            max_completion_tokens=kwargs.get("max_tokens", self._max_tokens),
            temperature=kwargs.get("temperature", 0.7),
        )
        
        message = response.choices[0].message
        
        if not message.tool_calls:
            raise ProviderError(
                "No tool call in response. The model did not return structured data."
            )
        
        tool_call = message.tool_calls[0]
        
        if hasattr(tool_call.function, 'parsed_arguments') and tool_call.function.parsed_arguments:
            return tool_call.function.parsed_arguments
        
        try:
            data = json.loads(tool_call.function.arguments)
            return schema.model_validate(data)
        except json.JSONDecodeError as e:
            raise ProviderError(
                f"Invalid tool arguments: {e}\nArguments were: {tool_call.function.arguments[:200]}"
            ) from e
        except Exception as e:
            raise ProviderError(f"Schema validation failed: {e}") from e

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
