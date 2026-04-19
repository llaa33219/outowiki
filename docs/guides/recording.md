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
