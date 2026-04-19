# Search Strategies

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
