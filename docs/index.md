# OutoWiki Documentation

OutoWiki is a wiki-based knowledge management system designed for AI agents. It provides a structured way to store, retrieve, and organize information that AI agents learn across interactions.

## Overview

OutoWiki solves the problem of persistent memory for AI agents by organizing information in a familiar wiki structure. Instead of opaque databases, OutoWiki uses markdown documents organized in folders, making the knowledge human-readable and editable.

### Wiki-Style Classification

OutoWiki follows Wikipedia/NamuWiki classification principles:

- **is-a Relationship** - Determine "What is this?" not "Is this similar?"
- **Category Tree Navigation** - Navigate hierarchical categories to find appropriate documents
- **No Similarity Matching** - Use topic understanding, not keyword matching
- **Explicit Document Linking** - Support `[[Document Name]]` syntax for direct connection

### Key Features

- **Folder-Based Classification** - Categories are folders, no preset categories forced
- **Dynamic Category Creation** - Create new categories as needed
- **Category Tree Exploration** - Navigate and explore category hierarchy
- **Required Title Validation** - title is REQUIRED for all documents, auto-retry if missing
- **LLM-Based Processing** - Keyword extraction, category matching, topic splitting all use LLM
- **Full Document Delivery** - Entire document content delivered to LLM (no 500-character limit)
- **Section-Based Editing** - Wikipedia-style section editing (append, prepend, replace)
- **Multi-Topic Splitting** - Split content with multiple topics using LLM
- **Wikilink Support** - Direct document connection via `[[Document Name]]` syntax

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
    │Recorder │  │Searcher │  │AgentLoop│
    │ Module  │  │ Module  │  │         │
    └────┬────┘  └────┬────┘  └────┬────┘
         │            │            │
    ┌────▼────────────▼────────────▼────┐
    │           LLM Provider            │
    │   (OpenAI or Anthropic)          │
    └──────────────────────────────────┘
```

The system has three main components:

- **Recorder**: Processes new content using Wiki-style topic classification (is-a relationship), determines document placement, manages backlinks
- **Searcher**: Finds relevant documents using semantic search and intent analysis
- **AgentLoop**: Unified LLM agent with tool-calling and conversation history, manages multi-turn tool chaining

### AgentLoop Architecture

OutoWiki uses a unified agent loop for LLM operations:

```
┌─────────────────────────────────────────────────────────┐
│                      AgentLoop                           │
│  (Manages conversation history and tool execution)       │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
    ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
    │Wiki I/O │  │Reasoning│  │ Tool    │
    │ Tools   │  │ Tools   │  │Registry │
    └─────────┘  └─────────┘  └─────────┘
```

**Key Benefits:**
- **Conversation History**: LLM sees previous results when planning
- **Tool Chaining**: LLM automatically chains tool calls
- **Context Continuity**: No redundant context injection
- **Automatic Progression**: No user intervention needed

**Example Flow:**
```python
result = agent_loop.run(
    user_message="Record this content to the wiki...",
    terminal_tools={"write_document"}
)
# LLM automatically: analyze → plan → generate_document → write_document
```

### Wiki Structure

OutoWiki organizes knowledge as markdown files in a folder hierarchy. **No preset categories are forced** - the wiki starts empty and categories are created dynamically as needed:

```
wiki/                    # Initially empty
├── programming/         # Created when first programming document is recorded
│   └── mobile/
│       └── camera.md
├── users/               # Created when first user document is recorded
│   └── alice/
│       └── preferences/
│           └── theme.md
└── ...                  # Categories grow organically
```

Each folder represents a category. When a document is recorded, the system:
1. Analyzes the content to determine its topic (is-a relationship)
2. Explores the existing category tree
3. Finds or creates the appropriate category folder
4. Records the document in that category

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
