# API Reference: Analysis Models

## IntentAnalysis

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

## AnalysisResult

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
