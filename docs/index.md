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

OutoWiki organizes knowledge as markdown files in a folder hierarchy:

```
wiki/
├── index.md              # Auto-generated category index
├── conversations/
│   ├── 2024-01-15_001.md
│   └── 2024-01-16_001.md
├── projects/
│   ├── project-alpha.md
│   └── notes/
│       └── planning.md
└── concepts/
    ├── python.md
    └── web-development.md
```

Documents support backlinks using the `[[Document Name]]` syntax. When `auto_backlinks` is enabled, OutoWiki automatically updates related documents when new content references existing topics.

## Installation

### Basic Installation

```bash
pip install outowiki
```

### Optional Dependencies

For full functionality with all providers:

```bash
# OpenAI support (included by default)
pip install outowiki[openai]

# Anthropic support
pip install outowiki[anthropic]

# All providers
pip install outowiki[all]
```

### Requirements

- Python 3.10 or higher
- An API key for your chosen LLM provider (OpenAI or Anthropic)

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

## Configuration

### WikiConfig

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

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `provider` | `Literal["openai", "anthropic"]` | `"openai"` | LLM provider to use |
| `base_url` | `str` | Provider default | API endpoint URL |
| `api_key` | `str` | `""` | API key for authentication |
| `model` | `str` | `"gpt-4"` | Model identifier |
| `max_output_tokens` | `int` | `4000` | Maximum tokens in LLM response |
| `wiki_path` | `str` | `"./wiki"` | Path to wiki folder |
| `settings` | `WikiSettings` | See WikiSettings | Behavior settings |

**Class Methods:**

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

### WikiSettings

Fine-tuning for wiki behavior.

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `token_threshold` | `int` | `4000` | Target tokens per document before splitting |
| `stub_threshold` | `int` | `300` | Minimum content before document is considered a stub |
| `auto_backlinks` | `bool` | `true` | Automatically update backlinks when recording |
| `auto_index` | `bool` | `true` | Auto-generate category index files |

## API Reference: OutoWiki Facade

The `OutoWiki` class is the main entry point. It provides a high-level interface for all wiki operations.

### Initialization

```python
wiki = OutoWiki(config: Optional[WikiConfig] = None)
```

Creates a new OutoWiki instance. If no config is provided, uses default settings (requires later configuration via `configure()`).

```python
# With config
wiki = OutoWiki(my_config)

# Without config - must call configure() before use
wiki = OutoWiki()
wiki.configure(provider="anthropic", api_key="sk-...")
```

### configure()

```python
wiki.configure(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    max_output_tokens: Optional[int] = None,
    wiki_path: Optional[str] = None
) -> None
```

Update configuration after initialization. Only specified parameters are updated.

```python
wiki.configure(api_key="sk-new-key...", model="gpt-4-turbo")
```

### record()

```python
wiki.record(
    content: Union[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None
) -> RecordResult
```

Record new information to the wiki. Content can be raw text or a dictionary with structured data.

```python
# Simple text
result = wiki.record("User mentioned they like Python programming")

# Structured content
result = wiki.record(
    content={
        "type": "user_preference",
        "topic": "programming_language",
        "value": "Python",
        "context": "web development"
    },
    metadata={"source": "conversation_2024_01_15"}
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `content` | `str` or `dict` | Content to record |
| `metadata` | `dict` | Optional metadata (source, timestamp, etc.) |

**Returns:** `RecordResult` with `success`, `actions_taken`, `documents_affected`, and optional `error`.

### search()

```python
wiki.search(
    query: Union[str, SearchQuery],
    category_filter: Optional[str] = None,
    max_results: int = 10,
    return_mode: str = "path"
) -> SearchResult
```

Search the wiki for relevant documents.

```python
# Simple text query
results = wiki.search("Python web frameworks")

# Detailed query with filters
results = wiki.search(
    SearchQuery(
        query="Django vs Flask",
        context="choosing a Python web framework",
        category_filter="concepts",
        max_results=5,
        return_mode="summary"
    )
)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` or `SearchQuery` | Required | Search query |
| `category_filter` | `str` | `None` | Limit to specific category folder |
| `max_results` | `int` | `10` | Maximum results to return |
| `return_mode` | `str` | `"path"` | Return `"path"`, `"summary"`, or `"full"` documents |

**Returns:** `SearchResult` containing paths, optional summaries, and optional full documents.

### get_document()

```python
wiki.get_document(path: str) -> WikiDocument
```

Retrieve a single document by path (relative to wiki root).

```python
doc = wiki.get_document("concepts/python.md")
print(doc.content)
print(doc.metadata.title)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Document path relative to wiki root |

**Returns:** `WikiDocument`

**Raises:** `OutoWikiError` if document not found.

### update_document()

```python
wiki.update_document(path: str, content: str) -> None
```

Update an existing document's content.

```python
wiki.update_document(
    "concepts/python.md",
    "# Python\n\nPython is a high-level programming language..."
)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Document path relative to wiki root |
| `content` | `str` | New markdown content |

**Raises:** `OutoWikiError` if document not found.

### delete_document()

```python
wiki.delete_document(path: str, remove_backlinks: bool = True) -> None
```

Delete a document from the wiki.

```python
# Delete and clean up backlinks
wiki.delete_document("concepts/old-topic.md")

# Delete without updating backlinks
wiki.delete_document("concepts/old-topic.md", remove_backlinks=False)
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | Required | Document path relative to wiki root |
| `remove_backlinks` | `bool` | `True` | Remove references from linking documents |

### list_categories()

```python
wiki.list_categories(folder: str = "") -> List[str]
```

List all category folders in the wiki.

```python
categories = wiki.list_categories()
# ["conversations", "projects", "concepts", "notes"]

# List subcategories within a category
subcats = wiki.list_categories("projects")
# ["alpha", "beta", "planning"]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder` | `str` | `""` | Parent folder to list from |

**Returns:** List of folder names (not full paths).

### list_documents()

```python
wiki.list_documents(folder: str = "") -> List[str]
```

List all documents in a category or subfolder.

```python
docs = wiki.list_documents()
# All documents in wiki

docs = wiki.list_documents("conversations")
# ["2024-01-15_001.md", "2024-01-16_001.md"]
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `folder` | `str` | `""` | Folder to list from (empty = wiki root) |

**Returns:** List of document filenames.

### wiki_path (property)

```python
path: Path
```

Read-only property returning the absolute path to the wiki folder.

```python
print(wiki.wiki_path)  # PosixPath('/home/user/my_wiki')
```

### provider (property)

```python
provider: LLMProvider
```

Read-only property returning the active LLM provider instance.

```python
print(type(wiki.provider))  # <class 'openai_provider.OpenAIProvider'>
```

## API Reference: Data Models

### RawContent

Represents raw content before processing.

```python
@dataclass
class RawContent:
    original: str
    metadata: Dict[str, Any]
    timestamp: datetime
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `original` | `str` | Raw text content |
| `metadata` | `dict` | Associated metadata |
| `timestamp` | `datetime` | When content was recorded |

### WikiDocument

A complete wiki document with content and metadata.

```python
@dataclass
class WikiDocument:
    path: str
    content: str
    metadata: DocumentMetadata
    links: List[str]
    backlinks: List[str]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `path` | `str` | Document path relative to wiki root |
| `content` | `str` | Markdown content |
| `metadata` | `DocumentMetadata` | Document metadata |
| `links` | `list[str]` | Paths this document links to |
| `backlinks` | `list[str]` | Paths linking to this document |

### DocumentMetadata

Metadata for a wiki document.

```python
@dataclass
class DocumentMetadata:
    title: str
    created: datetime
    modified: datetime
    category: str
    tags: List[str]
    summary: Optional[str]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Document title |
| `created` | `datetime` | Creation timestamp |
| `modified` | `datetime` | Last modification timestamp |
| `category` | `str` | Category folder |
| `tags` | `list[str]` | Associated tags |
| `summary` | `str` | Brief document summary |

### SearchQuery

Parameters for a detailed search.

```python
@dataclass
class SearchQuery:
    query: str
    context: Optional[str] = None
    category_filter: Optional[str] = None
    time_range: Optional[Tuple[datetime, datetime]] = None
    max_results: int = 10
    return_mode: str = "path"
```

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | `str` | Required | Search query string |
| `context` | `str` | `None` | Additional context for intent analysis |
| `category_filter` | `str` | `None` | Limit search to specific category |
| `time_range` | `tuple` | `None` | Filter by date range (start, end) |
| `max_results` | `int` | `10` | Maximum results |
| `return_mode` | `str` | `"path"` | Return mode: `"path"`, `"summary"`, or `"full"` |

### SearchResult

Results from a search operation.

```python
@dataclass
class SearchResult:
    paths: List[str]
    summaries: Optional[Dict[str, str]] = None
    documents: Optional[Dict[str, WikiDocument]] = None
    query_analysis: Optional[IntentAnalysis] = None
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `paths` | `list[str]` | Paths of matching documents |
| `summaries` | `dict` | Path to summary mapping (when return_mode includes summary) |
| `documents` | `dict` | Path to WikiDocument mapping (when return_mode is "full") |
| `query_analysis` | `IntentAnalysis` | Analysis of the search intent |

### RecordResult

Result of a record operation.

```python
@dataclass
class RecordResult:
    success: bool
    actions_taken: List[str]
    documents_affected: List[str]
    error: Optional[str]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether recording succeeded |
| `actions_taken` | `list[str]` | List of actions performed |
| `documents_affected` | `list[str]` | Documents created or modified |
| `error` | `str` | Error message if failed |

## API Reference: Plan Models

Plan models are used internally for complex operations like merging, splitting, and modifying documents.

### PlanType

Enum representing the type of plan.

```python
class PlanType(Enum):
    CREATE = "create"
    MODIFY = "modify"
    MERGE = "merge"
    SPLIT = "split"
    DELETE = "delete"
```

### Plan

Base class for all plans.

```python
@dataclass
class Plan:
    plan_type: PlanType
    rationale: str
    steps: List[PlanStep]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `plan_type` | `PlanType` | Type of plan |
| `rationale` | `str` | Why this plan was created |
| `steps` | `list[PlanStep]` | Steps to execute |

### CreatePlan

A plan for creating new documents.

```python
@dataclass
class CreatePlan(Plan):
    plan_type: PlanType = PlanType.CREATE
    target_path: str = ""
    initial_content: str = ""
```

### ModifyPlan

A plan for modifying existing documents.

```python
@dataclass
class ModifyPlan(Plan):
    plan_type: PlanType = PlanType.MODIFY
    target_path: str = ""
    modifications: List[str] = field(default_factory=list)
```

### MergePlan

A plan for merging multiple documents into one.

```python
@dataclass
class MergePlan(Plan):
    plan_type: PlanType = PlanType.MERGE
    source_paths: List[str] = field(default_factory=list)
    target_path: str = ""
    merge_strategy: str = "append"
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `source_paths` | `list[str]` | Documents to merge |
| `target_path` | `str` | Destination document |
| `merge_strategy` | `str` | How to merge: "append", "interleave", "replace" |

### SplitPlan

A plan for splitting a document into multiple parts.

```python
@dataclass
class SplitPlan(Plan):
    plan_type: PlanType = PlanType.SPLIT
    source_path: str = ""
    split_points: List[int] = field(default_factory=list)
    target_paths: List[str] = field(default_factory=list)
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `source_path` | `str` | Document to split |
| `split_points` | `list[int]` | Character offsets for split points |
| `target_paths` | `list[str]` | Destination paths for parts |

### DeletePlan

A plan for deleting documents.

```python
@dataclass
class DeletePlan(Plan):
    plan_type: PlanType = PlanType.DELETE
    target_paths: List[str] = field(default_factory=list)
    remove_backlinks: bool = True
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `target_paths` | `list[str]` | Documents to delete |
| `remove_backlinks` | `bool` | Whether to clean up backlinks |

## API Reference: Analysis Models

### IntentAnalysis

Analysis of search intent or content intent.

```python
@dataclass
class IntentAnalysis:
    primary_intent: str
    secondary_intents: List[str]
    entities: List[str]
    suggested_categories: List[str]
    confidence: float
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `primary_intent` | `str` | Main intent identified |
| `secondary_intents` | `list[str]` | Additional intents |
| `entities` | `list[str]` | Entities mentioned |
| `suggested_categories` | `list[str]` | Suggested category paths |
| `confidence` | `float` | Confidence score (0.0 to 1.0) |

### AnalysisResult

Result of analyzing content.

```python
@dataclass
class AnalysisResult:
    summary: str
    category: str
    tags: List[str]
    suggested_links: List[str]
    intent: IntentAnalysis
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `summary` | `str` | Content summary |
| `category` | `str` | Suggested category |
| `tags` | `list[str]` | Suggested tags |
| `suggested_links` | `list[str]` | Documents to link |
| `intent` | `IntentAnalysis` | Intent analysis |

## API Reference: Modules

### Recorder

The Recorder module handles processing and storing new content.

```python
from outowiki.modules import Recorder

recorder = Recorder(wiki_path, provider)
result = recorder.record(raw_content)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `record(content)` | Process and store new content |
| `analyze(content)` | Analyze content without storing |
| `categorize(content)` | Determine best category |

### Searcher

The Searcher module handles finding relevant documents.

```python
from outowiki.modules import Searcher

searcher = Searcher(wiki_path, provider)
results = searcher.search(query)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `search(query)` | Search with query string or SearchQuery |
| `semantic_search(query, k)` | Find semantically similar documents |
| `keyword_search(pattern)` | Find by keyword/pattern |

### InternalAgent

The InternalAgent handles complex wiki operations.

```python
from outowiki.modules import InternalAgent

agent = InternalAgent(wiki_path, provider)
plan = agent.analyze_intent(user_request)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `analyze_intent(request)` | Analyze user intent and create plan |
| `execute_plan(plan)` | Execute a plan |
| `merge(documents)` | Merge multiple documents |
| `split(document, points)` | Split document at points |

## API Reference: Providers

### LLMProvider (Abstract Base)

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

### OpenAIProvider

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

### AnthropicProvider

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

## API Reference: Exceptions

### OutoWikiError

Base exception for all OutoWiki errors.

```python
from outowiki.exceptions import OutoWikiError

try:
    wiki.record("content")
except OutoWikiError as e:
    print(f"Wiki error: {e}")
```

All other exceptions inherit from this base class.

### ConfigurationError

Raised for invalid configuration.

```python
from outowiki.exceptions import ConfigurationError

# Inherits from OutoWikiError
raise ConfigurationError("Invalid API key format")
```

### DocumentNotFoundError

Raised when a document cannot be found.

```python
from outowiki.exceptions import DocumentNotFoundError

try:
    doc = wiki.get_document("nonexistent.md")
except DocumentNotFoundError:
    print("Document not found")
```

### ProviderError

Raised when the LLM provider returns an error.

```python
from outowiki.exceptions import ProviderError

try:
    wiki.record("content")
except ProviderError as e:
    print(f"Provider error: {e}")
```

### PlanError

Raised when plan execution fails.

```python
from outowiki.exceptions import PlanError

# Inherited from OutoWikiError
raise PlanError("Cannot merge: documents incompatible")
```

### ValidationError

Raised for invalid input data.

```python
from outowiki.exceptions import ValidationError

# Inherited from OutoWikiError
raise ValidationError("SearchQuery.time_range requires (start, end) tuple")
```

## Guides

### Recording Workflow

The recording workflow processes new information through several stages:

```
Raw Content
    │
    ▼
┌─────────────────┐
│   Analysis      │  LLM analyzes content, extracts entities,
│                 │  determines category, suggests links
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Planning       │  Decide: create new, update existing,
│                 │  or merge with similar documents
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Execution     │  Create/update documents, manage backlinks,
│                 │  update indexes
└────────┬────────┘
         │
         ▼
    RecordResult
```

**Step 1: Analyze Content**

```python
from outowiki.modules import Recorder

recorder = Recorder(wiki.wiki_path, wiki.provider)
analysis = recorder.analyze("User prefers dark mode")
print(analysis.category)        # "preferences"
print(analysis.suggested_links)  # ["settings.md"]
```

**Step 2: Record with Metadata**

```python
result = wiki.record(
    content="User prefers dark mode for coding",
    metadata={
        "source": "conversation_2024_01_15",
        "entities": ["dark mode"],
        "preference_type": "ui"
    }
)

if result.success:
    print(f"Created: {result.documents_affected}")
else:
    print(f"Failed: {result.error}")
```

**Step 3: Verify Backlinks**

```python
# After recording, check that backlinks were created
doc = wiki.get_document("preferences/ui.md")
print(doc.backlinks)  # Should include conversation references
```

### Search Strategies

#### Basic Search

For simple queries, pass a string directly:

```python
results = wiki.search("python web development")
```

#### Category-Filtered Search

Limit results to a specific category:

```python
results = wiki.search(
    "authentication",
    category_filter="concepts/security"
)
```

#### Detailed Search with Context

Use `SearchQuery` for complex searches:

```python
from outowiki import SearchQuery
from datetime import datetime

results = wiki.search(
    SearchQuery(
        query="API design best practices",
        context="building a REST API",
        category_filter="concepts",
        time_range=(datetime(2024, 1, 1), datetime(2024, 12, 31)),
        max_results=10,
        return_mode="summary"
    )
)

# Access results
for path in results.paths:
    print(f"{path}: {results.summaries[path]}")
```

#### Full Document Retrieval

Get complete documents for detailed review:

```python
results = wiki.search(
    "python async programming",
    return_mode="full"
)

for path, doc in results.documents.items():
    print(f"=== {doc.metadata.title} ===")
    print(doc.content)
```

#### Iterative Refinement

Refine searches based on initial results:

```python
# Initial broad search
results = wiki.search("programming languages")

# Get full documents for analysis
detailed = wiki.search(
    SearchQuery(
        query="programming languages",
        max_results=5,
        return_mode="full"
    )
)

# Follow up with specific query based on findings
follow_up = wiki.search(
    f"Python compared to {', '.join([d.metadata.title for d in detailed.documents.values()[:3]])}"
)
```

#### Using Intent Analysis

The search returns intent analysis that explains how the query was interpreted:

```python
results = wiki.search("how do I handle errors in Python")

if results.query_analysis:
    print(f"Primary intent: {results.query_analysis.primary_intent}")
    print(f"Entities found: {results.query_analysis.entities}")
    print(f"Categories: {results.query_analysis.suggested_categories}")
```

### Document Management

#### Creating Documents

While `record()` is the preferred method, you can create documents directly:

```python
from pathlib import Path

doc_path = wiki.wiki_path / "concepts" / "new-topic.md"
doc_path.parent.mkdir(parents=True, exist_ok=True)

content = """# New Topic

Content here.

## Related

[[Related Document]]
"""

wiki.update_document("concepts/new-topic.md", content)
```

#### Updating Documents

```python
# Get current content
doc = wiki.get_document("concepts/python.md")

# Modify
new_content = doc.content + "\n\n## Additional Notes\n\nMore content."

# Write back
wiki.update_document("concepts/python.md", new_content)
```

#### Deleting Documents

```python
# Safe delete (removes backlinks)
wiki.delete_document("concepts/old-topic.md")

# Force delete without backlink cleanup
wiki.delete_document("concepts/old-topic.md", remove_backlinks=False)
```

#### Listing and Navigation

```python
# List all categories
categories = wiki.list_categories()

# List documents in a category
docs = wiki.list_documents("conversations")

# Navigate folder structure
for cat in wiki.list_categories():
    subcats = wiki.list_categories(cat)
    docs = wiki.list_documents(cat)
    print(f"{cat}/ ({len(subcats)} subcats, {len(docs)} docs)")
```
