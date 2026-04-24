"""Information search pipeline for OutoWiki (AgentLoop version)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ..models.search import SearchQuery, SearchResult
from ..models.content import WikiDocument
from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from .agent_loop import AgentLoop
from .wiki_tools import create_wiki_tools
from .reasoning_tools import create_reasoning_tools


SYSTEM_PROMPT = """You are a wiki search assistant. Your job is to find relevant documents for a search query.

You have access to these tools:
- list_categories: List all categories in the wiki
- list_folder: List files and folders in a directory
- read_document: Read a wiki document by path
- generate_summary: Generate a summary of content

Workflow:
1. Use list_categories to see available categories
2. Use list_folder to explore relevant categories
3. Use read_document to check document content
4. Return the paths of relevant documents

IMPORTANT: Search queries may contain MULTIPLE topics or subjects.
For example, "Python decorators and React hooks" contains TWO topics:
- Python decorators (likely in programming/python/)
- React hooks (likely in programming/javascript/react/)

When you encounter multiple topics:
1. Identify each distinct topic in the query
2. Search for each topic separately in its likely category
3. Collect documents for ALL topics
4. Return ALL relevant documents from ALL topics

When you have found all relevant documents, respond with a JSON object:
{{"paths": ["path/to/doc1.md", "path/to/doc2.md", ...]}}

Always use the tools to explore the wiki. Do not guess document paths - verify them first."""


class SearcherWithAgentLoop:
    """Information search pipeline using AgentLoop.

    LLM explores the wiki structure, reads documents, and selects
    the most relevant ones for the search query.

    Example:
        store = WikiStore("./wiki")
        agent_loop = AgentLoop(provider, tools, system_prompt)
        searcher = SearcherWithAgentLoop(store, agent_loop)

        results = searcher.search("user preferences")
        print(results.paths)  # ['users/alice/preferences.md', ...]
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

    def search(self, query: str | SearchQuery) -> SearchResult:
        if isinstance(query, str):
            search_query = SearchQuery(query=query)
        else:
            search_query = query

        self.logger.debug(f"Searching for: {search_query.query}")
        self.logger.debug(f"Search parameters: category={search_query.category_filter}, max_results={search_query.max_results}, mode={search_query.return_mode}")

        user_message = f"""Search the wiki for documents relevant to this query.

Query: {search_query.query}
Context: {search_query.context or 'General search'}
Max results: {search_query.max_results}

IMPORTANT: This query may contain MULTIPLE topics. Search for EACH topic separately and collect documents for ALL topics.

Explore the wiki structure, read documents to check relevance, and return the paths of the most relevant documents.
When you have found all relevant documents, respond with: {{"paths": ["path1", "path2", ...]}}"""

        self.agent_loop.reset()
        result = self.agent_loop.run(user_message=user_message)

        if result.truncated:
            self.logger.warning(f"Agent loop truncated after {result.steps} steps")

        paths = self._extract_paths_from_result(result.output)
        self.logger.debug(f"LLM found {len(paths)} documents: {paths}")

        search_result = SearchResult(paths=paths[:search_query.max_results])

        if search_query.return_mode in ['summary', 'full']:
            self.logger.debug("Generating summaries...")
            summaries: Dict[str, str] = {}
            for path in paths[:search_query.max_results]:
                try:
                    doc = self.wiki.read_document(path)
                    summary_result = self.agent_loop.run(
                        user_message=f"Generate a concise summary of this document:\n\n{doc.content[:1000]}",
                        terminal_tools={"generate_summary"},
                    )
                    if summary_result.output and isinstance(summary_result.output, dict):
                        summaries[path] = summary_result.output.get("summary", "Summary unavailable")
                    else:
                        summaries[path] = "Summary unavailable"
                except Exception as e:
                    self.logger.error(f"Failed to generate summary for {path}: {e}")
                    summaries[path] = "Summary unavailable"
            search_result.summaries = summaries

        if search_query.return_mode == 'full':
            self.logger.debug("Loading full documents...")
            documents: Dict[str, WikiDocument] = {}
            for path in paths[:search_query.max_results]:
                try:
                    documents[path] = self.wiki.read_document(path)
                    self.logger.debug(f"Loaded full document: {path}")
                except WikiStoreError as e:
                    self.logger.error(f"Failed to load document {path}: {e}")
            search_result.documents = documents

        self.logger.debug(f"Results ready: {len(search_result.paths)} paths")
        return search_result

    def _extract_paths_from_result(self, output: Any) -> List[str]:
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                return [output] if output else []
        
        if isinstance(output, dict):
            if "paths" in output:
                paths = output["paths"]
                if isinstance(paths, list):
                    return [p for p in paths if isinstance(p, str)]
            if "path" in output:
                path = output["path"]
                if isinstance(path, str):
                    return [path]
        if isinstance(output, list):
            return [p for p in output if isinstance(p, str)]
        return []
