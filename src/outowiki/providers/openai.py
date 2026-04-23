"""OpenAI-compatible LLM provider."""

import json
from typing import Any, TypeVar

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
from .base import LLMProvider, ProviderResponse, ToolCall

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

    def complete(self, prompt: str, **kwargs: Any) -> str:
        try:
            response = self.client.chat.completions.create(
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
        **kwargs: Any,
    ) -> T:
        tools = [pydantic_function_tool(schema)]
        
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        max_attempts = kwargs.get("max_attempts", 5)
        
        for attempt in range(max_attempts):
            response = self.client.chat.completions.parse(
                model=self._model,
                messages=messages,
                tools=tools,
                max_completion_tokens=kwargs.get("max_tokens", self._max_tokens),
                temperature=kwargs.get("temperature", 0.7),
            )
            
            message = response.choices[0].message
            
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                
                if hasattr(tool_call.function, 'parsed_arguments') and tool_call.function.parsed_arguments:
                    return schema.model_validate(tool_call.function.parsed_arguments)
                
                try:
                    data = json.loads(tool_call.function.arguments)
                    return schema.model_validate(data)
                except json.JSONDecodeError as e:
                    raise ProviderError(
                        f"Invalid tool arguments: {e}\nArguments were: {tool_call.function.arguments[:200]}"
                    ) from e
                except Exception as e:
                    raise ProviderError(f"Schema validation failed: {e}") from e
            
            if message.content:
                messages.append({"role": "assistant", "content": message.content})
            messages.append({
                "role": "user",
                "content": "You MUST use the provided tool. Do not describe what you will do - just call the tool immediately."
            })
        
        raise ProviderError(
            f"No tool call after {max_attempts} attempts. Last response: {message.content[:200] if message.content else 'empty'}"
        )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools,
                max_completion_tokens=kwargs.get("max_tokens", self._max_tokens),
                temperature=kwargs.get("temperature", 0.7),
            )
            
            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason or "stop"
            
            tool_calls = None
            if message.tool_calls:
                tool_calls = []
                for tc in message.tool_calls:
                    parsed = None
                    try:
                        parsed = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        pass
                    
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                        parsed_arguments=parsed,
                    ))
            
            return ProviderResponse(
                content=message.content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )
        except APIConnectionError as e:
            raise ProviderError(f"Connection error: {e}") from e
        except RateLimitError as e:
            raise ProviderError(f"Rate limit exceeded: {e}") from e
        except InternalServerError as e:
            raise ProviderError(f"Server error: {e}") from e
        except APIStatusError as e:
            raise ProviderError(f"API error {e.status_code}: {e.message}") from e

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
