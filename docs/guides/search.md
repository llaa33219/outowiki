# Search Strategies

## Overview

OutoWiki uses an **AgentLoop-based search pipeline** where the LLM autonomously explores the wiki to find relevant documents.

```
┌─────────────────────────────────────────────────────────────┐
│                    SearchQuery                               │
│  • query: str                                               │
│  • context: Optional[str]                                   │
│  • category_filter: Optional[str]                           │
│  • max_results: int                                         │
│  • return_mode: "path" | "summary" | "full"                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    SearcherWithAgentLoop                     │
│  • Passes query to AgentLoop                                │
│  • NO Python pre-processing                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      AgentLoop (LLM)                        │
│  LLM autonomously:                                          │
│  1. Analyzes search intent                                  │
│  2. Performs exact path matching                            │
│  3. Searches folders with relevance scoring                 │
│  4. Expands backlinks if needed                             │
│  5. Returns relevant document paths                         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    SearchResult                              │
│  • paths: List[str]                                         │
│  • summaries: Optional[Dict[str, str]]                      │
│  • documents: Optional[Dict[str, WikiDocument]]             │
│  • query_analysis: Optional[IntentAnalysis]                 │
└─────────────────────────────────────────────────────────────┘
```

## Search Flow (LLM Perspective)

When `search()` is called, the LLM receives the query and autonomously follows this workflow:

### 1. Intent Analysis
```
LLM calls analyze_search_intent tool:
- Input: query, context, available categories
- Output: IntentAnalysis (information_type, specificity_level, etc.)
- Determines search strategy
```

### 2. Exact Path Matching
```
LLM calls search_specific tool:
- Input: query, start_folder
- Normalizes query (spaces → underscores, lowercase)
- Checks exact path matches
- Returns matching document paths
```

### 3. Folder Search with Scoring
```
LLM calls search_folder_with_scoring tool:
- Input: folder, query, specificity_level
- Scores documents by relevance:
  • Title match: +0.5
  • Content match: +0.3
  • Tag match: +0.2
  • Category match: +0.1
- Includes documents scoring > 0.3
- Recurses into subfolders for general queries
```

### 4. Backlink Expansion (if high confidence needed)
```
LLM calls expand_backlinks tool:
- Input: document paths
- Finds documents that reference given paths
- Useful for discovering related content
```

## Available Tools for Search

### Wiki I/O Tools

| Tool | Description |
|------|-------------|
| `search_titles` | **FAST** - Search document titles by keyword |
| `list_categories` | List all categories in the wiki |
| `list_folder` | List files and folders in a directory |
| `read_document` | Read a wiki document by path |

### Reasoning Tools

| Tool | Description |
|------|-------------|
| `analyze_search_intent` | Analyze search query intent (calls LLM) |
| `generate_summary` | Generate document summary (calls LLM) |

### Searcher-Specific Tools

| Tool | Description |
|------|-------------|
| `search_specific` | Find documents by exact path matching |
| `search_folder_with_scoring` | Search folder with relevance scoring |
| `expand_backlinks` | Find documents that link to given paths |

## Search Modes

### Path Mode (Default)
Returns only document paths:

```python
results = wiki.search("python web development")
print(results.paths)  # ['programming/python/web.md', ...]
```

### Summary Mode
Returns paths with summaries:

```python
results = wiki.search("python web development", return_mode="summary")
for path in results.paths:
    print(f"{path}: {results.summaries[path]}")
```

### Full Mode
Returns paths with full document content:

```python
results = wiki.search("python web development", return_mode="full")
for path, doc in results.documents.items():
    print(f"=== {doc.title} ===")
    print(doc.content)
```

## Category-Filtered Search

Limit results to a specific category:

```python
results = wiki.search(
    "authentication",
    category_filter="concepts/security"
)
```

The LLM receives the category filter and restricts its search to that category.

## Multi-Topic Search

Search queries may contain multiple topics:

```python
# Query with multiple topics
results = wiki.search("Python decorators and React hooks")

# LLM identifies 2 topics:
# 1. "Python decorators" → searches for decorator-related documents
# 2. "React hooks" → searches for hook-related documents

# Returns documents from ALL topics
```

## Relevance Scoring

The `search_folder_with_scoring` tool uses this scoring formula:

```
Score = 0.0

if query in title (case-insensitive):
    Score += 0.5

if query in content (case-insensitive):
    Score += 0.3

if query in any tag (case-insensitive):
    Score += 0.2  (first match only)

if query in category (case-insensitive):
    Score += 0.1

Final Score = min(Score, 1.0)

Inclusion threshold: Score > 0.3
```

## Intent Analysis

The search returns intent analysis that explains how the query was interpreted:

```python
results = wiki.search("how do I handle errors in Python")

if results.query_analysis:
    print(f"Information type: {results.query_analysis.information_type}")
    print(f"Specificity: {results.query_analysis.specificity_level}")
    print(f"Temporal interest: {results.query_analysis.temporal_interest}")
    print(f"Exploration start: {results.query_analysis.exploration_start}")
    print(f"Confidence requirement: {results.query_analysis.confidence_requirement}")
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
    f"Python compared to {', '.join([d.title for d in detailed.documents.values()[:3]])}"
)
```
