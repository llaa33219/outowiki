"""Anthropic Claude LLM provider."""

from typing import Any, TypeVar

from anthropic import APIConnectionError, APIStatusError, Anthropic, RateLimitError
from pydantic import BaseModel

from ..core.exceptions import ProviderError
from .base import LLMProvider, ProviderResponse, ToolCall

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
        
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        max_attempts = kwargs.get("max_attempts", 5)
        
        for attempt in range(max_attempts):
            response = self.client.messages.create(
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
            )
            
            tool_use = None
            text_content = []
            
            for block in response.content:
                if block.type == "tool_use":
                    tool_use = block
                    break
                elif block.type == "text":
                    text_content.append(block.text)
            
            if tool_use:
                try:
                    return schema.model_validate(tool_use.input)
                except Exception as e:
                    error_details = str(e)
                    
                    if "list_type" in error_details:
                        error_msg = f"Validation error: {error_details}\nYou returned a STRING but an ARRAY is required. Return a JSON array like: [{{...}}, {{...}}]"
                    elif "missing" in error_details.lower() or "required" in error_details.lower():
                        error_msg = f"Validation error: {error_details}\nSome required fields are MISSING. Check the schema and provide ALL required fields."
                    elif "type=" in error_details:
                        error_msg = f"Validation error: {error_details}\nField types are INCORRECT. Check the schema and provide correct types."
                    else:
                        error_msg = f"Validation error: {error_details}\nPlease fix the errors above and try again."
                    
                    if text_content:
                        messages.append({"role": "assistant", "content": "\n".join(text_content)})
                    messages.append({"role": "user", "content": f"ERROR: {error_msg}"})
                    continue
            
            if text_content:
                messages.append({"role": "assistant", "content": "\n".join(text_content)})
            messages.append({
                "role": "user",
                "content": "You MUST use the provided tool. Do not describe what you will do - just call the tool immediately."
            })
        
        raise ProviderError(
            f"No tool call after {max_attempts} attempts."
        )

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        try:
            response = self.client.messages.create(
                model=self._model,
                max_tokens=kwargs.get("max_tokens", self._max_tokens),
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
            )
            
            content = None
            tool_calls = None
            
            for block in response.content:
                if block.type == "text":
                    content = (content or "") + block.text
                elif block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    
                    parsed = None
                    if isinstance(block.input, dict):
                        parsed = block.input
                    
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=str(block.input) if not isinstance(block.input, str) else block.input,
                        parsed_arguments=parsed,
                    ))
            
            return ProviderResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=response.stop_reason or "end_turn",
            )
        except APIConnectionError as e:
            raise ProviderError(f"Connection error: {e}") from e
        except RateLimitError as e:
            raise ProviderError(f"Rate limit exceeded: {e}") from e
        except APIStatusError as e:
            raise ProviderError(f"API error {e.status_code}") from e

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def max_tokens(self) -> int:
        return self._max_tokens
