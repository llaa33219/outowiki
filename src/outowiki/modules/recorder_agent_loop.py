"""Information recording pipeline for OutoWiki (AgentLoop version)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from .agent_loop import AgentLoop
from .wiki_tools import create_wiki_tools
from .reasoning_tools import create_reasoning_tools


SYSTEM_PROMPT = """You are a wiki recording assistant. Your job is to analyze content and record it to the wiki.

You have access to these tools:
- search_titles: Search document titles by keyword (FASTEST way to find existing documents)
- list_categories: List all categories in the wiki
- list_folder: List files and folders in a directory
- read_document: Read a wiki document by path
- write_document: Create or update a wiki document
- delete_document: Delete a wiki document
- generate_document: Generate document content from raw content

CRITICAL WORKFLOW - Follow this EXACTLY:
1. FIRST: Check for wikilinks like [[Document Name]]
   - If wikilink exists, read that document FIRST
   - If document exists, MODIFY it (append new content)
   - Do NOT create duplicate documents

2. SECOND: Use search_titles to find existing similar documents (FASTEST!)
   - Search for keywords from the content
   - This quickly finds documents with matching titles
   - Use this BEFORE exploring folders

3. THIRD: If search_titles finds a match:
   - Use read_document to verify the document exists and check content
   - If similar content exists, MODIFY it (append/prepend/replace section)
   - If no similar content, CREATE new document

4. FOURTH: If search_titles doesn't find a match:
   - Use list_categories to see available categories
   - Use list_folder to explore category structure
   - Create document in the most appropriate location

CRITICAL: VERIFY document exists BEFORE creating MODIFY plan
- ALWAYS use read_document to verify the document exists
- If document does NOT exist, use CREATE plan instead
- NEVER assume a document exists - always verify first

CRITICAL RULES - NEVER VIOLATE:
1. NEVER write content to category README.md files
   - README.md files are for category descriptions ONLY
   - Create SEPARATE topic-specific documents instead
   - Example: Write to "programming/python/decorators.md" NOT "programming/python/README.md"

2. NEVER put multiple topics in one document
   - Each topic gets its OWN document
   - Example: "Python decorators" → "programming/python/decorators.md"
   - Example: "React hooks" → "programming/javascript/react/hooks.md"
   - Do NOT combine them into one document

3. ALWAYS create specific, focused documents
   - Document should be about ONE specific topic
   - Use descriptive filenames: "decorators.md", "hooks.md", "camera_setup.md"
   - Do NOT use generic names like "notes.md", "info.md", "content.md"

4. TITLE is DIFFERENT from file path
   - Title is what users SEE when browsing the wiki
   - Title should be INTUITIVE and HUMAN-READABLE
   - Title should summarize the document's content clearly
   - File path is for organization, Title is for display

   IMPORTANT: Title should MATCH the filename (without .md extension)
   Examples:
   - Path: "programming/python/decorators" → Title: "decorators"
   - Path: "science/chemistry/elements/aluminum" → Title: "aluminum"
   - Path: "users/alice/preferences" → Title: "preferences"
   - Path: "tools/camera/react_native" → Title: "react_native"

   BAD titles (DO NOT USE):
   - "Python Decorators Guide" (doesn't match filename "decorators")
   - "Aluminum: Properties and Uses" (doesn't match filename "aluminum")
   - "Alice's Preferences" (doesn't match filename "preferences")
   - "React Native Camera Setup" (doesn't match filename "react_native")

IMPORTANT: Content may contain MULTIPLE topics.
For example: "Python decorators are useful. React hooks are powerful."
This contains TWO topics:
- Python decorators (programming/python/)
- React hooks (programming/javascript/react/)

When you encounter multiple topics:
1. Identify each distinct topic
2. Search for existing documents for EACH topic
3. Create SEPARATE document for EACH topic
4. Do NOT combine multiple topics into one document

When you have finished recording, respond with a JSON object:
{{"success": true, "actions": ["Created: path1", "Modified: path2"], "documents": ["path1", "path2"]}}

Always use the tools to explore the wiki. Do not guess - verify paths and content first."""


class RecordResult:
    """Result of a recording operation."""

    def __init__(
        self,
        success: bool,
        actions_taken: List[str],
        documents_affected: List[str],
        error: Optional[str] = None
    ):
        self.success = success
        self.actions_taken = actions_taken
        self.documents_affected = documents_affected
        self.error = error

    def __repr__(self) -> str:
        if self.success:
            return f"RecordResult(success=True, actions={self.actions_taken})"
        return f"RecordResult(success=False, error={self.error})"


class RecorderWithAgentLoop:
    """Information recording pipeline using AgentLoop.

    LLM analyzes content, explores wiki structure, and decides
    whether to create new documents or modify existing ones.

    Supports:
    - Multi-topic content: Each topic recorded separately
    - Existing document modification: Finds and updates related docs
    - Wikilink support: [[Document Name]] syntax for direct linking

    Example:
        store = WikiStore("./wiki")
        agent_loop = AgentLoop(provider, tools, system_prompt)
        recorder = RecorderWithAgentLoop(store, agent_loop)

        result = recorder.record("User prefers Python for web development")
        print(result.actions_taken)  # ['Created: users/preferences/python.md']
    """

    def __init__(self, wiki: WikiStore, agent_loop: AgentLoop, logger: Optional[logging.Logger] = None):
        self.wiki = wiki
        self.agent_loop = agent_loop
        self.logger = logger or logging.getLogger(__name__)
        
        self._register_tools()

    def _register_tools(self) -> None:
        for tool in create_wiki_tools(self.wiki):
            self.agent_loop.registry.register(tool)
        for tool in create_reasoning_tools():
            self.agent_loop.registry.register(tool)

    def record(
        self,
        content: str | Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> RecordResult:
        try:
            if isinstance(content, dict):
                raw_content = content.get('content', str(content))
                content_type = content.get('type', 'structured')
                context = content.get('context', {})
            else:
                raw_content = content
                content_type = metadata.get('type', 'conversation') if metadata else 'conversation'
                context = metadata.get('context', {}) if metadata else {}

            self.logger.debug(f"Recording content: {raw_content[:100]}...")
            self.logger.debug(f"Content type: {content_type}, Context: {context}")

            wikilinks = self._parse_wikilinks(raw_content)
            existing_docs = self._find_existing_documents(raw_content, wikilinks)
            categories = self._get_categories()
            recent_docs = self._get_recent_docs()

            user_message = f"""Record this content to the wiki:

Content:
{raw_content}

Content type: {content_type}

Wikilinks found: {wikilinks}
Existing related documents: {existing_docs}
Available categories: {categories}
Recent documents: {recent_docs}

CRITICAL: ALWAYS search for existing documents BEFORE creating new ones.
1. Check wikilinks first - if document exists, modify it
2. Search categories for similar documents
3. Only create new if no existing document covers this topic

IMPORTANT: This content may contain MULTIPLE topics. Process EACH topic separately.

Analyze the content, explore the wiki, and record ALL topics appropriately.
When finished, respond with: {{"success": true, "actions": [...], "documents": [...]}}"""

            self.agent_loop.reset()
            result = self.agent_loop.run(user_message=user_message)

            if result.truncated:
                self.logger.warning(f"Agent loop truncated after {result.steps} steps")

            actions, affected = self._extract_result(result.output, result.history)

            return RecordResult(
                success=len(actions) > 0,
                actions_taken=actions,
                documents_affected=affected,
            )

        except Exception as e:
            self.logger.error(f"Recording failed: {e}", exc_info=True)
            return RecordResult(
                success=False,
                actions_taken=[],
                documents_affected=[],
                error=str(e)
            )

    def _parse_wikilinks(self, content: str) -> List[str]:
        pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
        links = re.findall(pattern, content)
        self.logger.debug(f"Parsed wikilinks: {links}")
        return links

    def _find_existing_documents(self, content: str, wikilinks: List[str]) -> List[str]:
        existing = []
        
        for link in wikilinks:
            normalized = link.replace(' ', '_').lower()
            if self.wiki.document_exists(normalized):
                existing.append(normalized)
                self.logger.debug(f"Found via wikilink: {normalized}")
            elif self.wiki.document_exists(link):
                existing.append(link)
                self.logger.debug(f"Found via wikilink: {link}")
        
        return existing

    def _extract_result(self, output: Any, history: list[dict[str, Any]]) -> tuple[List[str], List[str]]:
        actions = []
        affected = set()
        
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                pass
        
        if isinstance(output, dict):
            if "actions" in output and isinstance(output["actions"], list):
                actions.extend([a for a in output["actions"] if isinstance(a, str)])
            if "documents" in output and isinstance(output["documents"], list):
                affected.update([d for d in output["documents"] if isinstance(d, str)])
        
        for msg in history:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get("success"):
                        path = data.get("path", "")
                        if path:
                            affected.add(path)
                except json.JSONDecodeError:
                    pass
        
        return actions, list(affected)

    def _get_categories(self, max_depth: int = 4) -> List[str]:
        categories: List[str] = []
        self._collect_categories("", categories, 0, max_depth)
        return categories

    def _collect_categories(self, path: str, categories: List[str], depth: int, max_depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            content = self.wiki.list_folder(path)
            for folder in content['folders']:
                folder_path = f"{path}/{folder}" if path else folder
                categories.append(folder_path)
                self._collect_categories(folder_path, categories, depth + 1, max_depth)
        except WikiStoreError:
            pass

    def _get_recent_docs(self) -> List[str]:
        try:
            md_files = list(self.wiki.root.rglob("*.md"))
            md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            docs = []
            for f in md_files[:10]:
                rel = f.relative_to(self.wiki.root)
                path_str = str(rel)
                if path_str.endswith('.md'):
                    path_str = path_str[:-3]
                docs.append(path_str)
            return docs
        except Exception:
            return []
