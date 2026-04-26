# Search Strategies

## Title Search (FASTEST)

The fastest way to find documents is by searching titles. Use `search_titles` for quick document discovery:

```python
# Title search is the FASTEST way to find documents
# It searches document titles by keyword
# Returns matching titles with their paths and categories
```

## Basic Search

For simple queries, pass a string directly:

```python
results = wiki.search("python web development")
```

## Category-Filtered Search

Limit results to a specific category:

```python
results = wiki.search(
    "authentication",
    category_filter="concepts/security"
)
```

## Multi-Topic Search

Search queries may contain multiple topics. The system searches for each topic separately and collects documents for all topics:

```python
# Query with multiple topics
results = wiki.search("Python decorators and React hooks")

# System identifies 2 topics:
# 1. "Python decorators" → searches for decorator-related documents
# 2. "React hooks" → searches for hook-related documents

# Returns documents from ALL topics
```

### How Multi-Topic Search Works

1. **Identify topics**: LLM identifies distinct topics in the query
2. **Search each topic**: Use `search_titles` for each topic separately
3. **Collect all results**: Combine documents from all topics
4. **Return relevant documents**: LLM selects most relevant ones

## Detailed Search with Context

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

## Full Document Retrieval

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

## Summary Generation

When `return_mode="summary"` or `return_mode="full"`, OutoWiki generates summaries using tool calls (function calling). This provides:

- **Structured output** - Guaranteed valid summary format
- **Type safety** - Pydantic schema validation
- **Consistency** - Summaries follow a defined structure

The `InternalAgent.generate_summary()` method returns `SummaryGeneration` schema via tool calls.

## Iterative Refinement

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

## Using Intent Analysis

The search returns intent analysis that explains how the query was interpreted:

```python
results = wiki.search("how do I handle errors in Python")

if results.query_analysis:
    print(f"Primary intent: {results.query_analysis.primary_intent}")
    print(f"Entities found: {results.query_analysis.entities}")
    print(f"Categories: {results.query_analysis.suggested_categories}")
```
