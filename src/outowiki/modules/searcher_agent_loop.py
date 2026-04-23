"""Information search pipeline for OutoWiki (AgentLoop version)."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..models.search import SearchQuery, SearchResult
from ..models.analysis import IntentAnalysis
from ..models.content import WikiDocument
from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from .agent_loop import AgentLoop
from .tools import ToolDefinition
from .wiki_tools import create_wiki_tools
from .reasoning_tools import create_reasoning_tools


SYSTEM_PROMPT = """You are a wiki search assistant. Your job is to analyze search queries and find relevant documents.

You have access to these tools:
- analyze_search_intent: Analyze search query intent
- read_document: Read a wiki document by path
- list_folder: List files and folders in a wiki directory
- list_categories: List all categories in the wiki
- generate_summary: Generate a summary of content

Workflow:
1. Analyze the search query to understand the intent
2. Explore the wiki structure to find relevant documents
3. Return the results with summaries if requested

Always use the tools provided. Do not describe what you will do - just do it."""


class SearcherWithAgentLoop:
    """Information search pipeline using AgentLoop.

    Processes search queries through intent analysis, document
    exploration, and result compilation.

    Pipeline:
        1. Analyze Intent: Understand what the user is looking for
        2. Explore: Navigate wiki structure to find relevant documents
        3. Return: Compile and format results

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

        categories = self._get_categories()

        user_message = f"""Search the wiki for relevant documents.

Query: {search_query.query}
Context: {search_query.context or 'General search'}
Available categories: {categories}

Find documents that match this query and return their paths."""

        self.agent_loop.reset()
        result = self.agent_loop.run(
            user_message=user_message,
            terminal_tools={"read_document"},
        )

        if result.truncated:
            self.logger.warning(f"Agent loop truncated after {result.steps} steps")

        paths = self._extract_paths_from_result(result.output)

        search_result = SearchResult(paths=paths[:search_query.max_results])

        if search_query.return_mode in ['summary', 'full']:
            self.logger.debug("Generating summaries...")
            summaries: Dict[str, str] = {}
            for path in paths[:search_query.max_results]:
                try:
                    doc = self.wiki.read_document(path)
                    summary_result = self.agent_loop.run(
                        user_message=f"Generate a summary of this document:\n\n{doc.content[:1000]}",
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

    def _extract_paths_from_result(self, output: any) -> List[str]:
        if isinstance(output, dict):
            if "paths" in output:
                return output["paths"]
            if "path" in output:
                return [output["path"]]
        if isinstance(output, list):
            return [p for p in output if isinstance(p, str)]
        if isinstance(output, str):
            return [output]
        return []

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
