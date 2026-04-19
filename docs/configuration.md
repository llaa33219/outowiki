# Configuration

## WikiConfig

The main configuration class for OutoWiki. Can be created directly or loaded from a YAML file.

```python
from outowiki import WikiConfig

# Direct creation
config = WikiConfig(
    provider="openai",
    api_key="sk-...",
    base_url="https://api.openai.com/v1",
    model="gpt-4",
    max_output_tokens=4000,
    wiki_path="./wiki",
    settings=WikiSettings(
        token_threshold=4000,
        stub_threshold=300,
        auto_backlinks=True,
        auto_index=True
    )
)
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `Literal["openai", "anthropic"]` | `"openai"` | LLM provider to use |
| `base_url` | `str` | Provider default | API endpoint URL |
| `api_key` | `str` | `""` | API key for authentication |
| `model` | `str` | `"gpt-4"` | Model identifier |
| `max_output_tokens` | `int` | `4000` | Maximum tokens in LLM response |
| `wiki_path` | `str` | `"./wiki"` | Path to wiki folder |
| `settings` | `WikiSettings` | See WikiSettings | Behavior settings |

### Class Methods

```python
# Load configuration from YAML file
config = WikiConfig.from_yaml("./config.yaml")

# Save configuration to YAML file
config.to_yaml("./config.yaml")
```

Example `config.yaml`:

```yaml
provider: openai
api_key: sk-...
model: gpt-4
max_output_tokens: 4000
wiki_path: ./wiki
settings:
  token_threshold: 4000
  stub_threshold: 300
  auto_backlinks: true
  auto_index: true
```

## WikiSettings

Fine-tuning for wiki behavior.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `token_threshold` | `int` | `4000` | Target tokens per document before splitting |
| `stub_threshold` | `int` | `300` | Minimum content before document is considered a stub |
| `auto_backlinks` | `bool` | `true` | Automatically update backlinks when recording |
| `auto_index` | `bool` | `true` | Auto-generate category index files |
