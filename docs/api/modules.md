# API Reference: Modules

## Architecture Overview

OutoWiki uses an **AgentLoop-based architecture** where the LLM autonomously handles all analysis, exploration, and decision-making.

```
┌─────────────────────────────────────────────────────────────┐
│                      OutoWiki Facade                         │
│  (Main entry point - delegates to AgentLoop-based modules)  │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         │                │                │
    ┌────▼─────┐   ┌──────▼──────┐   ┌─────▼─────┐
    │ Recorder │   │  Searcher   │   │ AgentLoop │
    │ WithLoop │   │  WithLoop   │   │           │
    └────┬─────┘   └──────┬──────┘   └─────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
    ┌─────────────────────▼─────────────────────┐
    │               Tool Registry               │
    │  ┌─────────┐ ┌──────────┐ ┌───────────┐  │
    │  │Wiki I/O │ │Reasoning │ │Specialized│  │
    │  │ Tools   │ │  Tools   │ │   Tools   │  │
    │  └─────────┘ └──────────┘ └───────────┘  │
    └─────────────────────┬─────────────────────┘
                          │
    ┌─────────────────────▼─────────────────────┐
    │              LLM Provider                 │
    │         (OpenAI or Anthropic)             │
    └───────────────────────────────────────────┘
```

## AgentLoop

The core component that manages LLM conversations and tool execution.

```python
from outowiki.modules.agent_loop import AgentLoop

agent_loop = AgentLoop(
    provider=provider,
    tools=all_tools,
    system_prompt="You are a wiki assistant...",
    max_iterations=80,
    logger=logger
)
```

**Key Features:**
- **Conversation History**: LLM sees previous tool results
- **Tool Chaining**: LLM automatically chains tool calls
- **Max Iterations**: Prevents infinite loops (default: 80)
- **Terminal Tools**: Specific tools that signal completion

**Methods:**

| Method | Description |
|--------|-------------|
| `run(user_message, context, terminal_tools)` | Execute the agent loop |
| `reset()` | Reset conversation history |

**Properties:**

| Property | Description |
|----------|-------------|
| `history` | Current conversation history |
| `registry` | Tool registry |

## RecorderWithAgentLoop

The recording pipeline uses AgentLoop for all processing.

```python
from outowiki.modules.recorder_agent_loop import RecorderWithAgentLoop

recorder = RecorderWithAgentLoop(wiki_store, agent_loop, logger)
result = recorder.record(content, metadata)
```

**Key Design:**
- **No Python pre-processing**: All analysis done by LLM
- **LLM-driven exploration**: LLM decides which tools to call
- **Autonomous decision-making**: LLM determines CREATE/MODIFY/MERGE/SPLIT/DELETE

**Methods:**

| Method | Description |
|--------|-------------|
| `record(content, metadata)` | Record content to wiki |

**RecordResult:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Whether recording succeeded |
| `actions_taken` | List[str] | List of actions performed |
| `documents_affected` | List[str] | Paths of affected documents |
| `error` | Optional[str] | Error message if failed |

## SearcherWithAgentLoop

The search pipeline uses AgentLoop for all exploration.

```python
from outowiki.modules.searcher_agent_loop import SearcherWithAgentLoop

searcher = SearcherWithAgentLoop(wiki_store, agent_loop, logger)
results = searcher.search(query)
```

**Key Design:**
- **No Python pre-processing**: All exploration done by LLM
- **LLM-driven search strategy**: LLM decides search approach
- **Relevance scoring**: LLM uses scoring tools for ranking

**Methods:**

| Method | Description |
|--------|-------------|
| `search(query)` | Search for documents |

**SearchResult:**

| Field | Type | Description |
|-------|------|-------------|
| `paths` | List[str] | Document paths found |
| `summaries` | Optional[Dict[str, str]] | Document summaries (if return_mode="summary") |
| `documents` | Optional[Dict[str, WikiDocument]] | Full documents (if return_mode="full") |
| `query_analysis` | Optional[IntentAnalysis] | How query was interpreted |

## Tool Reference

### Wiki I/O Tools (`wiki_tools`)

Basic wiki operations.

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `search_titles` | query, max_results | results[] | **FAST** - Search titles by keyword |
| `read_document` | path | title, content, tags, category, related | Read document |
| `write_document` | path, title, content, tags, category, related | path, success | Create/update document |
| `delete_document` | path, remove_backlinks | path, success | Delete document |
| `list_folder` | path | files[], folders[] | List folder contents |
| `list_categories` | max_depth | categories[] | List all categories (recursive) |

### Reasoning Tools (`reasoning_tools`)

Tools that call the LLM for analysis.

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `analyze_content` | content, content_type | AnalysisResult | Analyze raw content |
| `create_plan` | analysis, affected_docs, doc_summaries | PlanResponse | Create modification plans |
| `generate_document` | content, title, category, tags, related | DocumentGeneration | Generate document content |
| `generate_summary` | content | SummaryGeneration | Generate document summary |
| `analyze_search_intent` | query, context, categories | IntentAnalysis | Analyze search intent |

### Recorder-Specific Tools

Tools for document recording operations.

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `split_topics` | content | topics[], is_single_topic | Split content into topics (LLM) |
| `find_existing_document` | content, wikilinks | found_paths[], existing_contents{} | Find existing docs |
| `classify_topic` | content | category, is_new_category | Determine category (LLM) |
| `execute_create_plan` | title, content, category, tags, related | path, success, action | Create document (path auto-generated from title) |
| `execute_modify_plan` | target_path, modifications[] | path, success, action | Modify document |
| `execute_merge_plan` | target_path, source_paths[], merged_content, redirect_sources | path, success, action | Merge documents |
| `execute_split_plan` | target_path, sections_to_split[], summary_for_main | path, success, action | Split document |
| `execute_delete_plan` | target_path, remove_backlinks | path, success, action | Delete document |

### Searcher-Specific Tools

Tools for search operations.

| Tool | Input | Output | Description |
|------|-------|--------|-------------|
| `search_specific` | query, start_folder | paths[] | Exact path matching |
| `search_folder_with_scoring` | folder, query, specificity_level | paths[] | Relevance-scored search |
| `expand_backlinks` | paths[] | expanded_paths[] | Find backlinks |
| `return_search_results` | paths[] | paths[] | **Terminal tool** - Signals search completion and returns final results |

## Tool Details

### execute_modify_plan Operations

| Operation | Description |
|-----------|-------------|
| `append` | Add to end of document |
| `prepend` | Add to beginning of document |
| `append_section_after` | Add section after specific section |
| `replace_section` | Replace section content |

### search_folder_with_scoring Scoring

```
Score = 0.0
+ 0.5 if query in title
+ 0.3 if query in content
+ 0.2 if query in tag (first match)
+ 0.1 if query in category
= min(Score, 1.0)

Inclusion: Score > 0.3
```

### find_existing_document Search Order

1. Check wikilinks (`[[Document Name]]` pattern)
2. Normalize (spaces → underscores, lowercase)
3. If not found via wikilinks → category matching
4. Category matching explores up to 3 levels deep

## InternalAgent (Legacy)

The original InternalAgent is still available but deprecated in favor of AgentLoop-based modules.

```python
from outowiki.modules import InternalAgent

agent = InternalAgent(provider, logger)
analysis = agent.analyze(content)
plans = agent.plan(analysis)
```

**Methods:**

| Method | Description |
|--------|-------------|
| `analyze(content, content_type, context)` | Analyze content |
| `plan(analysis, affected_docs)` | Create modification plans |
| `generate_document(content, title, category, tags, related)` | Generate document |
| `generate_summary(content)` | Generate summary |

## Key Design Principles

### 1. LLM-Driven Processing

All analysis and decision-making is performed by the LLM, not Python pre-processing.

```python
# ❌ Old: Python pre-processes, then calls LLM
wikilinks = parse_wikilinks(content)  # Python
categories = get_categories()  # Python
result = llm.analyze(content, wikilinks, categories)  # LLM

# ✅ Current: LLM does everything autonomously
result = agent_loop.run(content)  # LLM uses tools as needed
```

### 2. Tool-Based Exploration

The LLM explores the wiki using tools, not Python code.

```python
# ❌ Old: Python explores
def find_document(content):
    for category in get_categories():
        if match(content, category):
            return category

# ✅ Current: LLM explores via tools
# LLM calls: search_titles → list_folder → read_document
```

### 3. Conversation History

The LLM sees all previous tool results in the conversation.

```python
# Step 1: LLM calls search_titles
# Step 2: LLM sees search_titles result, decides to call read_document
# Step 3: LLM sees read_document result, decides to call execute_modify_plan
# All steps are in conversation history
```

### 4. No Duplicate Processing

Single source of truth - the LLM handles everything.

```python
# ❌ Old: Double processing
wikilinks = parse_wikilinks(content)  # Python
# Then LLM also analyzes wikilinks

# ✅ Current: Single processing
# LLM analyzes and handles wikilinks via tools
```
