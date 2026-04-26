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

- **LLM-Driven Processing** - All analysis, exploration, and decision-making by LLM (no Python pre-processing)
- **AgentLoop Architecture** - Unified agent with tool-calling and conversation history
- **Folder-Based Classification** - Categories are folders, no preset categories forced
- **Dynamic Category Creation** - Create new categories as needed
- **Required Title Validation** - title is REQUIRED for all documents, auto-retry if missing
- **Title-Filename Consistency** - Document title must match filename (Wikipedia-style naming)
- **Fast Title Search** - `search_titles` tool for quick document discovery by title
- **Search-Before-Create** - Always search for existing documents before creating new ones
- **Full Document Delivery** - Entire document content delivered to LLM (no 500-character limit)
- **Section-Based Editing** - Wikipedia-style section editing (append, prepend, replace)
- **Multi-Topic Support** - Process multiple topics separately, create one document per topic
- **Wikilink Support** - Direct document connection via `[[Document Name]]` syntax
- **Version Tracking** - Automatic version saving for all document operations
- **Relevance Scoring** - Title/content/tag/category scoring for search results

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      OutoWiki Facade                     │
│  (OutoWiki class - main entry point for all operations)  │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
    ┌────▼─────────┐  ┌────▼────┐  ┌────▼────┐
    │   Recorder   │  │Searcher │  │AgentLoop│
    │  WithLoop    │  │WithLoop │  │         │
    └────┬─────────┘  └────┬────┘  └────┬────┘
         │                 │            │
         └─────────────────┼────────────┘
                           │
    ┌──────────────────────▼──────────────────────┐
    │              Tool Registry                   │
    │  ┌─────────┐ ┌──────────┐ ┌─────────────┐  │
    │  │Wiki I/O │ │Reasoning │ │ Specialized │  │
    │  │ Tools   │ │  Tools   │ │    Tools    │  │
    │  └─────────┘ └──────────┘ └─────────────┘  │
    └──────────────────────┬──────────────────────┘
                           │
    ┌──────────────────────▼──────────────────────┐
    │              LLM Provider                    │
    │         (OpenAI or Anthropic)                │
    └──────────────────────────────────────────────┘
```

The system has three main components:

- **RecorderWithAgentLoop**: Uses AgentLoop for all recording operations. LLM autonomously analyzes content, explores wiki structure, and decides whether to create/modify/merge/split/delete documents. **No Python pre-processing** - all decisions made by LLM.
- **SearcherWithAgentLoop**: Uses AgentLoop for all search operations. LLM autonomously explores the wiki using search tools, applies relevance scoring, and returns relevant documents.
- **AgentLoop**: Unified LLM agent with tool-calling and conversation history. Manages multi-turn tool chaining and maintains context across operations.

### AgentLoop Architecture

OutoWiki uses a unified agent loop for LLM operations. **All analysis, exploration, and decision-making is performed by the LLM** using tools.

```
┌─────────────────────────────────────────────────────────┐
│                      AgentLoop                           │
│  (Manages conversation history and tool execution)       │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
    ┌────▼────┐  ┌────▼────┐  ┌────▼────┐
    │Wiki I/O │  │Reasoning│  │Special- │
    │ Tools   │  │ Tools   │  │  ized   │
    │         │  │         │  │  Tools  │
    └─────────┘  └─────────┘  └─────────┘
```

**Key Benefits:**
- **LLM-Driven**: All decisions made by LLM, not Python pre-processing
- **Conversation History**: LLM sees previous tool results when planning next steps
- **Tool Chaining**: LLM automatically chains tool calls based on what it finds
- **No Duplication**: Single source of truth - LLM handles everything
- **Adaptive Strategy**: LLM adjusts approach based on wiki state

**Example Recording Flow:**
```python
result = recorder.record("User prefers Python for web development")
# LLM automatically:
# 1. Calls split_topics → identifies single topic
# 2. Calls search_titles → finds existing doc
# 3. Calls read_document → verifies content
# 4. Calls execute_modify_plan → appends new info
```

**Example Search Flow:**
```python
results = searcher.search("Python web frameworks")
# LLM automatically:
# 1. Calls analyze_search_intent → determines strategy
# 2. Calls search_specific → checks exact paths
# 3. Calls search_folder_with_scoring → finds relevant docs
# 4. Returns paths with relevance ranking
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
