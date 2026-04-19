# OutoWiki Documentation

OutoWiki is a wiki-based knowledge management system designed for AI agents. It provides a structured way to store, retrieve, and organize information that AI agents learn across interactions.

## Overview

OutoWiki solves the problem of persistent memory for AI agents by organizing information in a familiar wiki structure. Instead of opaque databases, OutoWiki uses markdown documents organized in folders, making the knowledge human-readable and editable.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      OutoWiki Facade                     │
│  (OutoWiki class - main entry point for all operations)  │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
    ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
    │Recorder │  │Searcher │  │Internal │
    │ Module  │  │ Module  │  │ Agent   │
    └────┬────┘  └────┬────┘  └────┬────┘
         │            │            │
    ┌────▼────────────▼────────────▼────┐
    │           LLM Provider            │
    │   (OpenAI or Anthropic)          │
    └──────────────────────────────────┘
```

The system has three main components:

- **Recorder**: Processes new content, determines document placement, manages backlinks
- **Searcher**: Finds relevant documents using semantic search and intent analysis
- **Internal Agent**: Handles complex operations like merge, split, and modify plans

### Wiki Structure

OutoWiki organizes knowledge as markdown files in a folder hierarchy. When initialized, default category folders are created automatically:

```
wiki/
├── users/
│   └── {username}/
│       ├── profile.md
│       └── preferences/
│           └── {topic}.md
├── tools/
│   └── {toolname}/
│       ├── overview.md
│       └── usage.md
├── agent/
│   ├── identity/
│   ├── learning/
│   └── memory/
├── knowledge/
│   └── {domain}/
│       └── {subdomain}/
│           └── {topic}.md
├── history/
│   └── sessions/
│       └── {date}.md
└── unassigned/
    └── {documents}.md
```

Documents support backlinks using the `[[Document Name]]` syntax. When `auto_backlinks` is enabled, OutoWiki automatically updates related documents when new content references existing topics.

## Quick Start

```python
from outowiki import OutoWiki, WikiConfig

# Create configuration
config = WikiConfig(
    provider="openai",
    api_key="sk-...",        # Your OpenAI API key
    model="gpt-4",
    wiki_path="./my_wiki"    # Local wiki folder
)

# Initialize the wiki
wiki = OutoWiki(config)

# Record new information
result = wiki.record({
    "type": "conversation",
    "content": "User prefers Python for web development. Suggested Flask or Django."
})
print(f"Recorded: {result.success}")
print(f"Actions: {result.actions_taken}")

# Search for information
results = wiki.search("programming preferences")
print(f"Found: {results.paths}")

# Work with a specific document
doc = wiki.get_document("concepts/web-development.md")
print(f"Title: {doc.metadata.title}")
print(doc.content[:500])
```

## Documentation

### Getting Started

- [Installation](installation.md) - How to install OutoWiki
- [Configuration](configuration.md) - Configuration options and settings

### API Reference

- [OutoWiki Facade](api/facade.md) - Main entry point for all operations
- [Data Models](api/models.md) - WikiDocument, SearchQuery, etc.
- [Plan Models](api/plans.md) - CreatePlan, ModifyPlan, MergePlan, etc.
- [Analysis Models](api/analysis.md) - IntentAnalysis, AnalysisResult
- [Modules](api/modules.md) - Recorder, Searcher, InternalAgent
- [Providers](api/providers.md) - OpenAI, Anthropic providers
- [Exceptions](api/exceptions.md) - Error handling

### Guides

- [Recording Workflow](guides/recording.md) - How to record information
- [Search Strategies](guides/search.md) - How to search effectively
- [Document Management](guides/documents.md) - CRUD operations

## License

Apache License 2.0 - see [LICENSE](../LICENSE) file for details.
