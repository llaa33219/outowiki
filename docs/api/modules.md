# API Reference: Modules

## Recorder

The Recorder module handles processing and storing new content using Wiki-style topic classification.

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
| `_classify_topic(content)` | Determine topic (is-a relationship) |
| `_find_document_in_category(category, content)` | Find document in category tree |
| `_explore_category_tree(category, depth, max_depth)` | Explore category tree structure |
| `_create_category_if_needed(category)` | Create category folder if it doesn't exist |
| `_parse_wikilinks(content)` | Extract `[[Document Name]]` patterns |
| `_split_topics(content)` | Split multi-topic content using LLM |
| `_extract_keywords(content)` | Extract keywords using LLM |
| `_category_matches(category, keywords)` | Match category to keywords using LLM |
| `_append_section_after(content, section, new_content)` | Add section after specific section |

### Wiki-Style Topic Classification

The Recorder uses **is-a relationship** to determine document placement:

```python
# Explore category tree
tree = recorder._explore_category_tree()
print(tree)
# {
#   'category': '',
#   'files': [],
#   'subcategories': [
#     {'category': 'programming', 'files': ['python.md'], 'subcategories': [...]},
#     {'category': 'users', 'files': [], 'subcategories': [...]}
#   ]
# }

# Determine topic (is-a relationship)
topic = recorder._classify_topic("카메라 앱 개발 중 Expo Camera 사용")
print(topic)  # "programming/mobile/camera"

# Create category if needed
created = recorder._create_category_if_needed("programming/mobile/camera")
print(created)  # True if created, False if already exists

# Find document in category
doc_path = recorder._find_document_in_category("programming/mobile/camera", content)
print(doc_path)  # "programming/mobile/camera.md" or None
```

### Title Requirement

**title is REQUIRED for all document creation plans.** If LLM generates a plan without title, the system automatically retries with explicit instruction:

```python
# LLM must provide title in metadata
plan = CreatePlan(
    target_path="tools/camera",
    reason="New camera tool documentation",
    content="...",
    metadata=DocumentMetadata(
        title="React Native Camera Setup",  # REQUIRED
        tags=["camera", "react-native"],
        category="tools"
    )
)

# If title is missing, system retries automatically:
# "IMPORTANT: You MUST provide a title in metadata.title for EVERY plan. Title is REQUIRED."
```

### Folder-Based Classification

Categories are **folders**. No preset categories are forced:

```python
# Initially empty wiki
# Record first document
wiki.record("Python decorators are useful")
# → Creates: programming/python/decorators.md

# Record second document
wiki.record("React hooks are powerful")
# → Creates: programming/javascript/react_hooks.md

# Categories grow organically
tree = recorder._explore_category_tree()
# Shows: programming/python/, programming/javascript/
```

### Wikilink Support

```python
# Parse wikilinks from content
links = recorder._parse_wikilinks("See [[React Native Camera]] for details")
print(links)  # ["React Native Camera"]

# Direct document connection
# If document exists, record directly in that document
```

### Multi-Topic Splitting

```python
# Split content with multiple topics
topics = recorder._split_topics("""
## Topic 1
Content for topic 1

## Topic 2
Content for topic 2
""")
print(len(topics))  # 2
```

### Section-Based Editing

```python
# Add new section after "Known Issues"
new_content = recorder._append_section_after(
    existing_content,
    "Known Issues",
    "## Performance Notes\n\nImage caching improves performance."
)
```

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
| `generate_document(content, title, category, tags, related)` | Generate document via tool calls |
| `generate_summary(content)` | Generate summary via tool calls |

## Key Design Principles

### 1. is-a Relationship (Wiki-Style)

The system determines **"What is this?"** instead of similarity matching:

```python
# ❌ Previous: Similarity matching
score = calculate_similarity(content, existing_docs)
if score > threshold:
    append_to_document()

# ✅ Current: Topic classification
topic = classify_topic(content)  # "What is this?"
category = find_category(topic)  # Navigate category tree
document = find_document_in_category(category)
```

### 2. Full Document Delivery

When modifying existing documents, the **entire content** is delivered:

```python
# ❌ Previous: 500 character limit
doc.content[:500]

# ✅ Current: Full document
doc.content
```

### 3. No Similarity Matching

| Approach | Method |
|----------|--------|
| ❌ Similarity | `_content_matches()`, `_title_matches()`, `_get_ngrams()` |
| ✅ Wiki-Style | `_classify_topic()`, `_find_document_in_category()` |

### 4. Explicit Document Linking

Support for `[[Document Name]]` syntax for direct document connection:

```python
# Direct connection via wikilink
wiki.record("See [[React Native Camera]] for implementation")
# → Directly records in "React Native Camera" document if exists
```
