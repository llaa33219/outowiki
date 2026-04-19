# Document Management

## Creating Documents

While `record()` is the preferred method, you can create documents directly:

```python
from pathlib import Path

doc_path = wiki.wiki_path / "concepts" / "new-topic.md"
doc_path.parent.mkdir(parents=True, exist_ok=True)

content = """# New Topic

Content here.

## Related

[[Related Document]]
"""

wiki.update_document("concepts/new-topic.md", content)
```

## Updating Documents

```python
# Get current content
doc = wiki.get_document("concepts/python.md")

# Modify
new_content = doc.content + "\n\n## Additional Notes\n\nMore content."

# Write back
wiki.update_document("concepts/python.md", new_content)
```

## Deleting Documents

```python
# Safe delete (removes backlinks)
wiki.delete_document("concepts/old-topic.md")

# Force delete without backlink cleanup
wiki.delete_document("concepts/old-topic.md", remove_backlinks=False)
```

## Listing and Navigation

```python
# List all categories
categories = wiki.list_categories()

# List documents in a category
docs = wiki.list_documents("conversations")

# Navigate folder structure
for cat in wiki.list_categories():
    subcats = wiki.list_categories(cat)
    docs = wiki.list_documents(cat)
    print(f"{cat}/ ({len(subcats)} subcats, {len(docs)} docs)")
```
