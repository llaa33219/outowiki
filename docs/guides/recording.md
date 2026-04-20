# Recording Workflow

The recording workflow processes new information through several stages:

```
Raw Content
    │
    ▼
┌─────────────────┐
│   Analysis      │  LLM analyzes content, determines topic
│                 │  (is-a relationship), finds category
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Topic Search   │  Navigate category tree to find
│                 │  appropriate existing document
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

## Wiki-Style Document Classification

OutoWiki follows Wikipedia/NamuWiki classification principles:

### Core Principle: is-a Relationship

The system determines **"What is this?"** (is-a relationship) instead of similarity matching:

```
"카메라 앱 개발 중 Expo Camera 라이브러리를 사용했다"
→ This is "카메라 앱 개발" (camera app development)
→ Find category: programming/mobile/camera
→ Record in existing document or create new
```

### Classification Algorithm

```python
def _classify_topic(content: str) -> Optional[str]:
    # 1. Explore category tree
    category_tree = self._explore_category_tree()
    
    # 2. Ask LLM with category tree information
    # "What is this?" (is-a relationship)
    # LLM considers existing categories and suggests best fit
    
    # 3. Create category if needed
    if suggested_category not in existing_categories:
        self._create_category_if_needed(suggested_category)
    
    # 4. Return category path
    return suggested_category
```

### Category Tree Exploration

The system explores the existing category tree before classification:

```python
def _explore_category_tree(self, category: str = "", depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
    # Recursively explore folder structure
    # Returns tree with files and subcategories
    # Example output:
    # {
    #   'category': 'programming',
    #   'files': ['python.md', 'javascript.md'],
    #   'subcategories': [
    #     {'category': 'programming/mobile', 'files': ['camera.md'], ...}
    #   ]
    # }
```

### Dynamic Category Creation

When no appropriate category exists, the system creates it automatically:

```python
def _create_category_if_needed(self, category: str) -> bool:
    # 1. Check if category exists
    # 2. Create parent categories if needed (recursively)
    # 3. Create category folder
    # 4. Create README.md for the category
    # Example: "programming/mobile/camera" creates:
    #   - programming/ folder
    #   - programming/mobile/ folder
    #   - programming/mobile/camera/ folder
    #   - programming/mobile/camera/README.md
```

### No Similarity Matching

| Previous Approach | Wiki Approach |
|-------------------|---------------|
| Keyword extraction → similarity calculation → matching | Topic identification → category navigation → document finding |
| "Is this similar?" | "What is this?" |
| Create new document on match failure | Find appropriate category and record |

## Wikilink Support

OutoWiki supports `[[Document Name]]` syntax for explicit document linking:

```python
# Direct document reference
wiki.record("카메라 앱 개발에 대해 [[React Native Camera]]를 사용했다")
# → Directly links to "React Native Camera" document

# Alternative display text
wiki.record("[[카메라 앱|Camera App Development]] 시작")
# → Links to "카메라 앱" but displays "Camera App Development"
```

### How Wikilinks Work

1. **Parse wikilinks**: Extract `[[Document Name]]` patterns
2. **Direct connection**: If document exists, record directly in that document
3. **Create if missing**: If document doesn't exist, create new document

## Full Document Delivery

When modifying an existing document, the **entire document content** is delivered to the LLM:

```python
# Previous: 500 character limit
affected_docs[doc_path] = doc.content[:500]  # ❌ Limited context

# Current: Full document
affected_docs[doc_path] = doc.content  # ✅ Complete context
```

This ensures the LLM has full context when determining where to add new information.

## Section-Based Editing

OutoWiki supports Wikipedia-style section editing:

### Available Operations

| Operation | Description | Example |
|-----------|-------------|---------|
| `append` | Add to end of document | `doc.content += new_content` |
| `prepend` | Add to beginning of document | `doc.content = new_content + doc.content` |
| `append_section_after` | Add new section after specific section | Insert after "## Known Issues" |
| `replace_section` | Replace entire section content | Update "## Installation" section |

### Example: Append Section After

```python
# Add new section after "Known Issues" section
plan = ModifyPlan(
    target_path="camera_app.md",
    modifications=[{
        "section": "Known Issues",
        "operation": "append_section_after",
        "content": "## Performance Notes\n\nImage caching improves performance."
    }]
)
```

## Multi-Topic Splitting

When input contains multiple topics, each is processed independently:

```python
# Input with multiple topics
content = """
## 카메라 앱 개발
Expo Camera 라이브러리를 사용한다.

## 성능 최적화
이미지 캐싱을 추가했다.

## 배포 준비
App Store 심사를 준비 중이다.
"""

# Each topic processed separately:
# 1. "카메라 앱 개발" → programming/mobile/camera
# 2. "성능 최적화" → programming/performance
# 3. "배포 준비" → deployment/app_store
```

### Splitting Algorithm

```python
def _split_topics(content: str) -> List[str]:
    # 1. Split by headers (## 제목)
    # 2. Split by [제목] patterns
    # 3. Split by topic transition keywords
    # 4. Return list of topic blocks
```

## Step-by-Step Recording

### Step 1: Topic Classification

```python
from outowiki.modules import Recorder

recorder = Recorder(wiki.wiki_path, wiki.provider)
topic = recorder._classify_topic("User prefers dark mode")
print(topic)  # "preferences/ui"
```

### Step 2: Find Existing Document

```python
# Find document in category
doc_path = recorder._find_document_in_category("preferences/ui", content)
print(doc_path)  # "preferences/ui/theme.md" or None
```

### Step 3: Record with Metadata

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

### Step 4: Verify Backlinks

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

### Frontmatter Handling

Document metadata (created, modified dates) is managed automatically by the system. LLM-generated content may include YAML frontmatter, but it is stripped during processing—only the body content is kept. The system always generates fresh `created` and `modified` timestamps when writing documents.

## Document Classification Rules

OutoWiki follows hierarchical classification guidelines inspired by Wikipedia and NamuWiki:

### Core Principles

1. **is-a Relationship** - Determine "What is this?" not "Is this similar?"
2. **Most Specific Category** - Place documents in the lowest-level matching category
3. **Hierarchical Structure** - Categories form a tree (folders = categories)
4. **No Similarity Matching** - Use topic understanding, not keyword matching
5. **No Preset Categories** - Categories are created dynamically as needed
6. **Folder-Based** - Each folder is a category, no separate category system

### How Categories Work

Categories are **folders**. When you record a document:
1. System analyzes content to determine topic
2. Explores existing folder structure
3. Finds or creates appropriate folder
4. Records document in that folder

```python
# Example: Recording "카메라 앱 개발 중 Expo Camera 사용"
# 1. Topic: "카메라 앱 개발" (camera app development)
# 2. Category: "programming/mobile/camera"
# 3. If folders don't exist:
#    - Create: programming/
#    - Create: programming/mobile/
#    - Create: programming/mobile/camera/
# 4. Record: programming/mobile/camera/expo_camera.md
```

### Category Naming Rules

- Use lowercase with underscores: `web_development`, `python_basics`
- Use singular nouns: `tool` not `tools` (folder name is exception)
- Be specific: `programming/python/web` not `programming/stuff`
- Use `/` for hierarchy: `domain/subdomain/topic`

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

# Good: Topic classification (is-a)
wiki.record("카메라 앱 개발 중 Expo Camera 사용")
# → knowledge/programming/mobile/camera.md (is-a: camera app development)

# Avoid: Too shallow
wiki.record("Python decorators")  # Don't create at knowledge/python.md

# Avoid: Too deep
# knowledge/programming/languages/python/frameworks/django/rest/serializers.md
# Instead: knowledge/programming/python/django_serializers.md
```

## Handling Fragmented Information

When information arrives in multiple chunks:

### Scenario 1: Related Chunks

```python
# Chunk 1: "카메라 앱 개발 시작"
# → Create: knowledge/programming/mobile/camera.md

# Chunk 2: "Expo Camera 라이브러리 사용"
# → Topic: "카메라 앱 개발" (same topic)
# → Find existing document
# → Append to: knowledge/programming/mobile/camera.md

# Chunk 3: "iOS와 Android 모두 지원"
# → Topic: "카메라 앱 개발" (same topic)
# → Find existing document
# → Append to: knowledge/programming/mobile/camera.md
```

### Scenario 2: Unrelated Chunks

```python
# Chunk 1: "카메라 앱 개발 시작"
# → Create: knowledge/programming/mobile/camera.md

# Chunk 2: "데이터베이스 최적화 방법"
# → Topic: "데이터베이스 최적화" (different topic)
# → Create: knowledge/database/optimization.md

# Chunk 3: "사용자 인증 시스템 구현"
# → Topic: "사용자 인증" (different topic)
# → Create: knowledge/security/authentication.md
```

### Key Insight

The system determines **"What is this?"** (is-a relationship) for each chunk:
- Same topic → Append to existing document
- Different topic → Create new document

No similarity matching or content comparison is used.
