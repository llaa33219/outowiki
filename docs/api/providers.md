# API Reference: Providers

## LLMProvider (Abstract Base)

Base class for all LLM providers.

```python
from outowiki.providers import LLMProvider

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    def analyze(self, content: str, task: str) -> dict:
        pass
```

**Common Methods:**

| Method | Description |
|--------|-------------|
| `complete(prompt, **kwargs)` | Generate completion |
| `analyze(content, task)` | Analyze content for a task |
| `set_api_key(key)` | Update API key |
| `get_model()` | Get current model name |

## OpenAIProvider

OpenAI API provider using GPT models.

```python
from outowiki.providers import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4",
    base_url="https://api.openai.com/v1",
    max_output_tokens=4000
)
```

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | Required | OpenAI API key |
| `model` | `"gpt-4"` | Model to use |
| `base_url` | OpenAI default | API endpoint |
| `max_output_tokens` | `4000` | Max response tokens |

## AnthropicProvider

Anthropic API provider using Claude models.

```python
from outowiki.providers import AnthropicProvider

provider = AnthropicProvider(
    api_key="sk-ant-...",
    model="claude-3-opus-20240229",
    max_output_tokens=4000
)
```

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | Required | Anthropic API key |
| `model` | `"claude-3-opus-20240229"` | Model to use |
| `max_output_tokens` | `4000` | Max response tokens |
