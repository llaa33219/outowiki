"""Information recording pipeline for OutoWiki (AgentLoop version)."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from ..models.content import WikiDocument
from ..models.analysis import AnalysisResult
from ..models.plans import Plan, PlanType, CreatePlan, ModifyPlan, MergePlan, SplitPlan, DeletePlan
from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from ..utils.markdown import extract_sections, parse_frontmatter
from .agent_loop import AgentLoop
from .tools import ToolDefinition
from .wiki_tools import create_wiki_tools
from .reasoning_tools import create_reasoning_tools


SYSTEM_PROMPT = """You are a wiki recording assistant. Your job is to analyze content, create plans, and execute wiki operations.

You have access to these tools:
- analyze_content: Analyze raw content and extract structured information
- create_plan: Create modification plans based on analysis
- generate_document: Generate document content from raw content
- read_document: Read a wiki document by path
- write_document: Create or update a wiki document
- delete_document: Delete a wiki document
- list_folder: List files and folders in a wiki directory
- list_categories: List all categories in the wiki

Workflow:
1. Analyze the content to understand what information it contains
2. Create a plan for how to record this information
3. Execute the plan by creating, modifying, or deleting documents

Always use the tools provided. Do not describe what you will do - just do it."""


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

    Processes raw content through analysis, planning, and execution
    to update the wiki with new information.

    Pipeline:
        1. Analyze: Extract structured information from raw input
        2. Plan: Determine what wiki operations to perform
        3. Execute: Apply the plans to update documents

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

            categories = self._get_categories()
            recent_docs = self._get_recent_docs()

            user_message = f"""Record this content to the wiki:

Content:
{raw_content}

Content type: {content_type}

Available categories: {categories}
Recent documents: {recent_docs}

Analyze the content, create a plan, and execute it."""

            self.agent_loop.reset()
            result = self.agent_loop.run(
                user_message=user_message,
                terminal_tools={"write_document", "delete_document"},
            )

            if result.truncated:
                self.logger.warning(f"Agent loop truncated after {result.steps} steps")

            actions = self._extract_actions_from_history(result.history)
            affected = self._extract_affected_from_history(result.history)

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

    def _extract_actions_from_history(self, history: list[dict[str, Any]]) -> list[str]:
        actions = []
        for msg in history:
            if msg.get("role") == "tool":
                tool_call_id = msg.get("tool_call_id", "")
                content = msg.get("content", "")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get("success"):
                        path = data.get("path", "")
                        if path:
                            actions.append(f"Modified: {path}")
                except json.JSONDecodeError:
                    pass
        return actions

    def _extract_affected_from_history(self, history: list[dict[str, Any]]) -> list[str]:
        affected = set()
        for msg in history:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        path = data.get("path", "")
                        if path:
                            affected.add(path)
                except json.JSONDecodeError:
                    pass
        return list(affected)

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
