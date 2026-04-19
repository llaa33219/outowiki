# API Reference: Providers

## LLMProvider (Abstract Base)

Base class for all LLM providers.

```python
from outowiki.providers import LLMProvider
from pydantic import BaseModel

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        """Get completion from LLM."""
        pass

    @abstractmethod
    def complete_with_schema(self, prompt: str, schema: type[BaseModel], **kwargs) -> BaseModel:
        """Get structured completion using tool calling."""
        pass
```

**Common Methods:**

| Method | Description |
|--------|-------------|
| `complete(prompt, **kwargs)` | Generate text completion |
| `complete_with_schema(prompt, schema, **kwargs)` | Generate structured completion using tool calling |

## OpenAIProvider

OpenAI API provider using GPT models with tool calling support.

```python
from outowiki.providers import OpenAIProvider
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int

provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4",
    base_url="https://api.openai.com/v1",
    max_output_tokens=4000
)

# Structured completion using tool calling
result = provider.complete_with_schema("Extract user info: John is 30", UserInfo)
print(result.name)  # "John"
print(result.age)   # 30
```

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | Required | OpenAI API key |
| `model` | `"gpt-4"` | Model to use |
| `base_url` | OpenAI default | API endpoint |
| `max_output_tokens` | `4000` | Max response tokens |

**Tool Calling:**
- Uses `pydantic_function_tool` for schema conversion
- Calls `client.chat.completions.parse()` for structured responses
- Returns parsed Pydantic model directly

## AnthropicProvider

Anthropic API provider using Claude models with tool calling support.

```python
from outowiki.providers import AnthropicProvider
from pydantic import BaseModel

class UserInfo(BaseModel):
    name: str
    age: int

provider = AnthropicProvider(
    api_key="sk-ant-...",
    model="claude-3-opus-20240229",
    max_output_tokens=4000
)

# Structured completion using tool calling
result = provider.complete_with_schema("Extract user info: John is 30", UserInfo)
print(result.name)  # "John"
print(result.age)   # 30
```

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | Required | Anthropic API key |
| `model` | `"claude-3-opus-20240229"` | Model to use |
| `max_output_tokens` | `4000` | Max response tokens |

**Tool Calling:**
- Uses `tools` parameter with `input_schema`
- Parses `ToolUseBlock` from response
- Returns validated Pydantic model
