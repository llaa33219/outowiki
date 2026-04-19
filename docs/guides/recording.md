# Recording Workflow

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

## Step 1: Analyze Content

```python
from outowiki.modules import Recorder

recorder = Recorder(wiki.wiki_path, wiki.provider)
analysis = recorder.analyze("User prefers dark mode")
print(analysis.category)        # "preferences"
print(analysis.suggested_links)  # ["settings.md"]
```

## Step 2: Record with Metadata

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

## Step 3: Verify Backlinks

```python
# After recording, check that backlinks were created
doc = wiki.get_document("preferences/ui.md")
print(doc.backlinks)  # Should include conversation references
```

## Document Generation

OutoWiki uses tool calls (function calling) for document generation instead of parsing text responses. This provides:

- **Structured output** - Guaranteed valid markdown format
- **Type safety** - Pydantic schema validation
- **Reliability** - No parsing errors from free-form text

The `InternalAgent.generate_document()` method returns `DocumentGeneration` schema via tool calls.

## Document Classification Rules

OutoWiki follows hierarchical classification guidelines inspired by 나무위키 and Wikipedia:

### Core Principles

1. **Every document must have a category** - Documents without classification are placed in `unassigned/`
2. **Most specific category** - Place documents in the lowest-level matching category
3. **Hierarchical structure** - Categories form a tree up to 4 levels deep

### Default Category Structure

```
wiki/
├── users/{username}/           # User profiles and preferences
│   ├── profile.md
│   └── preferences/{topic}.md
├── tools/{toolname}/           # Tool knowledge and usage
│   ├── overview.md
│   └── usage.md
├── agent/{aspect}/             # Agent self-knowledge
│   ├── identity/
│   ├── learning/{topic}.md
│   └── memory/
├── knowledge/{domain}/{sub}/   # General knowledge
│   └── {topic}.md
├── history/{type}/             # Conversation logs
│   └── sessions/{date}.md
└── unassigned/                 # Fallback for uncategorized
```

### Category Naming Rules

- Use lowercase with underscores: `web_development`, `python_basics`
- Use singular nouns: `tool` not `tools` (folder name is exception)
- Be specific: `knowledge/programming/python` not `knowledge/stuff`

### When to Create Subcategories

- **20+ documents** in a parent category → Create subcategories
- **Shared characteristic** among 5+ documents → Consider subcategory
- **Max depth**: 4 levels (prevent over-nesting)

### Examples

```python
# Good: Specific category path
wiki.record("Python decorators are useful for metaprogramming")
# → knowledge/programming/python/decorators.md

# Good: User-specific content
wiki.record("Alice prefers dark theme and vim keybindings")
# → users/alice/preferences/ide.md

# Avoid: Too shallow
wiki.record("Python decorators")  # Don't create at knowledge/python.md

# Avoid: Too deep
# knowledge/programming/languages/python/frameworks/django/rest/serializers.md
# Instead: knowledge/programming/python/django_serializers.md
```
