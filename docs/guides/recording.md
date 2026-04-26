# Recording Workflow

## Overview

OutoWiki uses an **AgentLoop-based recording pipeline** where the LLM autonomously analyzes content, explores the wiki, and makes all decisions about document creation/modification.

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input (raw content)                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    RecorderWithAgentLoop                     │
│  • Basic input parsing (dict/string, type, context)         │
│  • Passes raw content to AgentLoop                          │
│  • NO Python pre-processing                                 │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      AgentLoop (LLM)                        │
│  LLM autonomously:                                          │
│  1. Analyzes content and identifies topics                  │
│  2. Searches for existing documents                         │
│  3. Explores category tree                                  │
│  4. Decides CREATE/MODIFY/MERGE/SPLIT/DELETE                │
│  5. Executes appropriate tools                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      RecordResult                           │
│  • success: bool                                            │
│  • actions_taken: List[str]                                 │
│  • documents_affected: List[str]                            │
│  • error: Optional[str]                                     │
└─────────────────────────────────────────────────────────────┘
```

## Key Design Principle: LLM-Driven Processing

**All analysis and decision-making is performed by the LLM**, not Python pre-processing.

| Aspect | Old Approach | Current Approach |
|--------|--------------|------------------|
| Wikilink parsing | Python regex | LLM uses `find_existing_document` tool |
| Category exploration | Python recursive scan | LLM uses `list_categories` tool |
| Existing doc search | Python search | LLM uses `search_titles` tool |
| Topic classification | Python + LLM call | LLM uses `classify_topic` tool |
| Decision making | Fixed pipeline | LLM autonomously decides |

**Why LLM-Driven?**
- **More accurate**: LLM understands semantic meaning better than regex/pattern matching
- **More flexible**: LLM adapts strategy based on what it finds
- **No duplication**: Single source of truth (LLM), not Python + LLM double processing
- **Better context**: LLM sees all tool results in conversation history

## Recording Flow (LLM Perspective)

When `record()` is called, the LLM receives a simple message and autonomously follows this workflow:

### 1. Content Analysis
```
LLM analyzes the raw content:
- Identifies topics (single or multiple)
- Understands content type and context
- Determines appropriate actions
```

### 2. Topic Splitting (if needed)
```
LLM calls split_topics tool:
- Input: raw content
- Output: list of separated topics
- If multiple topics → process each separately
```

### 3. For Each Topic
```
LLM searches for existing documents:
- Calls find_existing_document (checks wikilinks + categories)
- OR calls search_titles for keyword search
- OR calls list_categories to explore structure

If existing document found:
  → Calls read_document to verify content
  → Calls execute_modify_plan to update

If no existing document:
  → Calls classify_topic to determine category
  → Calls execute_create_plan to create new
```

### 4. Complex Operations
```
For MERGE: execute_merge_plan
For SPLIT: execute_split_plan
For DELETE: execute_delete_plan
```

## Available Tools for Recording

### Wiki I/O Tools

| Tool | Description |
|------|-------------|
| `search_titles` | **FAST** - Search document titles by keyword |
| `list_categories` | List all categories in the wiki (recursive, depth 4) |
| `list_folder` | List files and folders in a directory |
| `read_document` | Read a wiki document by path |
| `write_document` | Create or update a wiki document |
| `delete_document` | Delete a wiki document |

### Reasoning Tools

| Tool | Description |
|------|-------------|
| `analyze_content` | Analyze raw content (calls LLM) |
| `create_plan` | Create modification plans (calls LLM) |
| `generate_document` | Generate document content (calls LLM) |
| `generate_summary` | Generate summary (calls LLM) |

### Recorder-Specific Tools

| Tool | Description |
|------|-------------|
| `split_topics` | Split content into multiple topics (calls LLM) |
| `find_existing_document` | Find existing docs via wikilinks + category matching |
| `classify_topic` | Determine which category content belongs to (calls LLM) |
| `execute_create_plan` | Create new document with validation + version tracking |
| `execute_modify_plan` | Modify document (append/prepend/replace_section) |
| `execute_merge_plan` | Merge multiple documents |
| `execute_split_plan` | Split document into sub-documents |
| `execute_delete_plan` | Delete document with version tracking |

## Critical Rules

### 1. Search-Before-Create
**ALWAYS** search for existing documents BEFORE creating new ones.

### 2. Single Topic Per Document
- Each topic gets its OWN document
- NEVER combine multiple topics in one document

### 3. No README.md Writes
- NEVER write content to category README.md files
- README.md files are for category descriptions ONLY

### 4. Title-Filename Consistency
```
Title: "Python Classes" → Filename: python_classes.md
Title: "React Native Camera" → Filename: react_native_camera.md
```

### 5. English Titles and Tags
- Title and tags MUST be in English
- Content can be in any language

## Section-Based Editing

The `execute_modify_plan` tool supports Wikipedia-style section editing:

| Operation | Description |
|-----------|-------------|
| `append` | Add to end of document |
| `prepend` | Add to beginning of document |
| `append_section_after` | Add new section after specific section |
| `replace_section` | Replace entire section content |

## Multi-Topic Handling

When content contains multiple topics:

```python
content = """
Python decorators are useful for metaprogramming.
React hooks are powerful for state management.
"""

# LLM identifies 2 topics:
# 1. "Python decorators" → programming/python/decorators.md
# 2. "React hooks" → programming/javascript/react/hooks.md

result = wiki.record(content)
# result.actions_taken = ["Created: programming/python/decorators.md", 
#                         "Created: programming/javascript/react/hooks.md"]
```

## Version Tracking

All document operations automatically save versions:

| Operation | Version Type |
|-----------|--------------|
| Create | `create` |
| Modify | `modify` |
| Merge | `merge` |
| Split | `split` |
| Delete | `delete` |

Versions can be retrieved and rolled back using the WikiStore API.
