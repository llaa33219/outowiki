"""Unit tests for LLM providers (OpenAI and Anthropic)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from outowiki.core.exceptions import ProviderError
from outowiki.providers.anthropic import AnthropicProvider
from outowiki.providers.base import LLMProvider
from outowiki.providers.openai import OpenAIProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class SampleSchema(BaseModel):
    """Simple schema used in complete_with_schema tests."""

    name: str
    value: int


# ---------------------------------------------------------------------------
# LLMProvider abstract base
# ---------------------------------------------------------------------------


class TestLLMProviderBase:
    """Tests for the abstract LLMProvider base class."""

    def test_cannot_instantiate_directly(self):
        """LLMProvider is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_concrete_subclass_can_instantiate(self):
        """A subclass that implements all abstract methods can be instantiated."""

        class ConcreteProvider(LLMProvider):
            def complete(self, prompt: str, **kwargs: object) -> str:
                return ""

            def complete_with_schema(self, prompt: str, schema: type, **kwargs: object):
                return schema()

            @property
            def model_name(self) -> str:
                return "test"

            @property
            def max_tokens(self) -> int:
                return 0

        provider = ConcreteProvider()
        assert provider.model_name == "test"
        assert provider.max_tokens == 0


# ---------------------------------------------------------------------------
# OpenAIProvider
# ---------------------------------------------------------------------------


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialisation and properties."""

    @patch("outowiki.providers.openai.OpenAI")
    def test_init_with_defaults(self, mock_openai_cls):
        """Provider initialises with default model and max_tokens."""
        provider = OpenAIProvider(api_key="test-key")
        mock_openai_cls.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            max_retries=3,
        )
        assert provider.model_name == "gpt-4"
        assert provider.max_tokens == 4000

    @patch("outowiki.providers.openai.OpenAI")
    def test_init_with_custom_params(self, mock_openai_cls):
        """Provider passes custom base_url, model, and max_tokens."""
        provider = OpenAIProvider(
            api_key="k",
            base_url="http://localhost:8000",
            model="gpt-3.5-turbo",
            max_tokens=2048,
        )
        mock_openai_cls.assert_called_once_with(
            api_key="k",
            base_url="http://localhost:8000",
            max_retries=3,
        )
        assert provider.model_name == "gpt-3.5-turbo"
        assert provider.max_tokens == 2048


class TestOpenAIProviderComplete:
    """Tests for OpenAIProvider.complete()."""

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_returns_string(self, mock_openai_cls):
        """complete() returns the message content from the response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "hello world"

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.create.return_value = mock_response

        result = provider.complete("say hi")
        assert result == "hello world"
        provider.client.chat.completions.create.assert_called_once()

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_passes_kwargs(self, mock_openai_cls):
        """complete() forwards temperature and max_tokens kwargs."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.create.return_value = mock_response

        provider.complete("prompt", temperature=0.2, max_tokens=500)

        call_kwargs = provider.client.chat.completions.create.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.2
        assert call_kwargs.kwargs.get("max_completion_tokens") == 500

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_handles_none_content(self, mock_openai_cls):
        """complete() returns empty string when content is None."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.create.return_value = mock_response

        result = provider.complete("prompt")
        assert result == ""

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_raises_on_connection_error(self, mock_openai_cls):
        """complete() raises ProviderError on APIConnectionError."""
        from openai import APIConnectionError

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        with pytest.raises(ProviderError, match="Connection error"):
            provider.complete("prompt")

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_raises_on_rate_limit(self, mock_openai_cls):
        """complete() raises ProviderError on RateLimitError."""
        from openai import RateLimitError

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.create.side_effect = RateLimitError(
            message="rate limited",
            response=MagicMock(),
            body=MagicMock(),
        )

        with pytest.raises(ProviderError, match="Rate limit"):
            provider.complete("prompt")

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_raises_on_api_status_error(self, mock_openai_cls):
        """complete() raises ProviderError on APIStatusError."""
        from openai import APIStatusError

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.create.side_effect = APIStatusError(
            message="bad request",
            response=MagicMock(status_code=400),
            body=MagicMock(),
        )

        with pytest.raises(ProviderError, match="API error"):
            provider.complete("prompt")


class TestOpenAIProviderCompleteWithSchema:
    """Tests for OpenAIProvider.complete_with_schema()."""

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_with_schema_returns_model(self, mock_openai_cls):
        """complete_with_schema uses tool calling and returns a validated model."""
        payload = {"name": "alice", "value": 42}

        mock_tool_call = MagicMock()
        mock_tool_call.function.parsed_arguments = SampleSchema(**payload)

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = mock_message

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.parse.return_value = mock_response

        result = provider.complete_with_schema("describe", SampleSchema)
        assert isinstance(result, SampleSchema)
        assert result.name == "alice"
        assert result.value == 42

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_with_schema_raises_on_no_tool_call(self, mock_openai_cls):
        """complete_with_schema raises ProviderError when no tool call in response."""
        mock_message = MagicMock()
        mock_message.tool_calls = []

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = mock_message

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.parse.return_value = mock_response

        with pytest.raises(ProviderError, match="No tool call in response"):
            provider.complete_with_schema("describe", SampleSchema)

    @patch("outowiki.providers.openai.OpenAI")
    def test_complete_with_schema_uses_tools_parameter(self, mock_openai_cls):
        """complete_with_schema passes tools parameter to API."""
        mock_tool_call = MagicMock()
        mock_tool_call.function.parsed_arguments = SampleSchema(name="test", value=1)

        mock_message = MagicMock()
        mock_message.tool_calls = [mock_tool_call]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = mock_message

        provider = OpenAIProvider(api_key="k")
        provider.client.chat.completions.parse.return_value = mock_response

        provider.complete_with_schema("my prompt", SampleSchema)

        call_args = provider.client.chat.completions.parse.call_args
        assert "tools" in call_args.kwargs
        assert len(call_args.kwargs["tools"]) == 1
        messages = call_args.kwargs["messages"]
        assert "my prompt" in messages[0]["content"]


# ---------------------------------------------------------------------------
# AnthropicProvider
# ---------------------------------------------------------------------------


class TestAnthropicProviderInit:
    """Tests for AnthropicProvider initialisation and properties."""

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_init_with_defaults(self, mock_anthropic_cls):
        """Provider initialises with default model and max_tokens."""
        provider = AnthropicProvider(api_key="test-key")
        mock_anthropic_cls.assert_called_once_with(
            api_key="test-key",
            base_url=None,
            max_retries=2,
        )
        assert provider.model_name == "claude-sonnet-4-20250514"
        assert provider.max_tokens == 4000

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_init_with_custom_params(self, mock_anthropic_cls):
        """Provider passes custom base_url, model, and max_tokens."""
        provider = AnthropicProvider(
            api_key="k",
            base_url="http://localhost:8080",
            model="claude-3-haiku-20240307",
            max_tokens=1024,
        )
        mock_anthropic_cls.assert_called_once_with(
            api_key="k",
            base_url="http://localhost:8080",
            max_retries=2,
        )
        assert provider.model_name == "claude-3-haiku-20240307"
        assert provider.max_tokens == 1024

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_init_default_url_passes_none(self, mock_anthropic_cls):
        """When base_url is the default, None is passed to Anthropic client."""
        AnthropicProvider(api_key="k")
        mock_anthropic_cls.assert_called_once_with(
            api_key="k",
            base_url=None,
            max_retries=2,
        )


class TestAnthropicProviderComplete:
    """Tests for AnthropicProvider.complete()."""

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_returns_string(self, mock_anthropic_cls):
        """complete() returns the text from the first content block."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hello from claude")]

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.return_value = mock_response

        result = provider.complete("say hi")
        assert result == "hello from claude"
        provider.client.messages.create.assert_called_once()

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_passes_kwargs(self, mock_anthropic_cls):
        """complete() forwards max_tokens kwarg."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="ok")]

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.return_value = mock_response

        provider.complete("prompt", max_tokens=100)

        call_kwargs = provider.client.messages.create.call_args
        assert call_kwargs.kwargs.get("max_tokens") == 100

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_raises_on_connection_error(self, mock_anthropic_cls):
        """complete() raises ProviderError on APIConnectionError."""
        from anthropic import APIConnectionError

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        with pytest.raises(ProviderError, match="Connection error"):
            provider.complete("prompt")

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_raises_on_rate_limit(self, mock_anthropic_cls):
        """complete() raises ProviderError on RateLimitError."""
        from anthropic import RateLimitError

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.side_effect = RateLimitError(
            message="rate limited",
            response=MagicMock(),
            body=MagicMock(),
        )

        with pytest.raises(ProviderError, match="Rate limit"):
            provider.complete("prompt")

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_raises_on_api_status_error(self, mock_anthropic_cls):
        """complete() raises ProviderError on APIStatusError."""
        from anthropic import APIStatusError

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.side_effect = APIStatusError(
            message="server error",
            response=MagicMock(status_code=500),
            body=MagicMock(),
        )

        with pytest.raises(ProviderError, match="API error"):
            provider.complete("prompt")


class TestAnthropicProviderCompleteWithSchema:
    """Tests for AnthropicProvider.complete_with_schema()."""

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_with_schema_returns_model(self, mock_anthropic_cls):
        """complete_with_schema uses tool calling and returns a validated model."""
        payload = {"name": "bob", "value": 99}

        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.input = payload

        mock_response = MagicMock()
        mock_response.content = [mock_tool_use]

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.return_value = mock_response

        result = provider.complete_with_schema("describe", SampleSchema)
        assert isinstance(result, SampleSchema)
        assert result.name == "bob"
        assert result.value == 99

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_with_schema_raises_on_no_tool_call(self, mock_anthropic_cls):
        """complete_with_schema raises ProviderError when no tool_use in response."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "some text"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.return_value = mock_response

        with pytest.raises(ProviderError, match="No tool call in response"):
            provider.complete_with_schema("describe", SampleSchema)

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_with_schema_uses_tools_parameter(self, mock_anthropic_cls):
        """complete_with_schema passes tools parameter to API."""
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.input = {"name": "test", "value": 1}

        mock_response = MagicMock()
        mock_response.content = [mock_tool_use]

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.return_value = mock_response

        provider.complete_with_schema("my prompt", SampleSchema)

        call_args = provider.client.messages.create.call_args
        assert "tools" in call_args.kwargs
        assert len(call_args.kwargs["tools"]) == 1

    @patch("outowiki.providers.anthropic.Anthropic")
    def test_complete_with_schema_raises_on_invalid_json(self, mock_anthropic_cls):
        """complete_with_schema raises ProviderError on non-tool response."""
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "not valid json"

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        provider = AnthropicProvider(api_key="k")
        provider.client.messages.create.return_value = mock_response

        with pytest.raises(ProviderError, match="No tool call in response"):
            provider.complete_with_schema("describe", SampleSchema)
