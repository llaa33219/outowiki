<p align="center">
  <img src="logo.svg" alt="OutoWiki Logo" width="200">
</p>

# OutoWiki - AI Agent Knowledge Management Wiki

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://pypi.org/project/outowiki/)
[![Apache 2.0 License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![PyPI Version](https://img.shields.io/pypi/v/outowiki.svg)](https://pypi.org/project/outowiki/)

OutoWiki is a wiki-based knowledge management system designed for AI agents. It provides a structured way to store, retrieve, and organize information that AI agents learn across interactions.

## Features

- **Folder-based wiki structure** with markdown documents
- **LLM-powered information processing** (OpenAI, Anthropic)
- **Automatic document classification and organization**
- **Backlink system** for document relationships
- **Document merge/split** with Wiki rules

## Installation

```bash
pip install outowiki
```

## Quick Start

```python
from outowiki import OutoWiki, WikiConfig

# Configuration
config = WikiConfig(
    provider="openai",
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-5.2",
    max_output_tokens=4000,
    wiki_path="./my_wiki"
)

# Initialize
wiki = OutoWiki(config)

# Record information
result = wiki.record("""
User: I prefer Python for web development
Agent: Great! Flask and Django are popular choices.
""")

# Search information
results = wiki.search("user programming preferences")
print(results.paths)
```

## Configuration

Configure OutoWiki using `WikiConfig`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `provider` | LLM provider ("openai" or "anthropic") | required |
| `base_url` | API endpoint URL | provider default |
| `api_key` | API key for authentication | required |
| `model` | Model identifier | provider default |
| `max_output_tokens` | Maximum output tokens for LLM response | 4000 |
| `wiki_path` | Path to wiki directory | "./wiki" |

## API Reference

For detailed API documentation, see [docs/index.md](docs/index.md).

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.
