# API Reference: OutoWiki Facade

The `OutoWiki` class is the main entry point. It provides a high-level interface for all wiki operations.

## Initialization

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

## configure()

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

## record()

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

## search()

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

## get_document()

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

## update_document()

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

## delete_document()

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

## list_categories()

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

## list_documents()

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

## wiki_path (property)

```python
path: Path
```

Read-only property returning the absolute path to the wiki folder.

```python
print(wiki.wiki_path)  # PosixPath('/home/user/my_wiki')
```

## provider (property)

```python
provider: LLMProvider
```

Read-only property returning the active LLM provider instance.

```python
print(type(wiki.provider))  # <class 'openai_provider.OpenAIProvider'>
```
