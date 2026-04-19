# API Reference: Data Models

## RawContent

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

## WikiDocument

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

## DocumentMetadata

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

## SearchQuery

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

## SearchResult

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

## RecordResult

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
