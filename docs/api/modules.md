# API Reference: Modules

## Recorder

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

## Searcher

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

## InternalAgent

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
