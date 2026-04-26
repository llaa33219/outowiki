"""Information search pipeline for OutoWiki (AgentLoop version)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..models.search import SearchQuery, SearchResult
from ..models.analysis import IntentAnalysis
from ..models.content import WikiDocument
from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from .agent_loop import AgentLoop
from .tools import ToolDefinition
from .wiki_tools import create_wiki_tools
from .reasoning_tools import create_reasoning_tools


SYSTEM_PROMPT = """You are a wiki search assistant. Your job is to find relevant documents for a search query.

You have access to these tools:
- search_titles: Search document titles by keyword (FASTEST way to find documents)
- list_categories: List all categories in the wiki
- list_folder: List files and folders in a directory
- read_document: Read a wiki document by path
- search_specific: Find documents by exact path matching
- search_folder_with_scoring: Search folder with relevance scoring (title +0.5, content +0.3, tag +0.2, category +0.1)
- expand_backlinks: Find documents that link to given paths
- analyze_search_intent: Determine search strategy from query

CRITICAL WORKFLOW:
1. FIRST: Use analyze_search_intent to understand what to search for
   - Determines specificity level and where to start looking

2. SECOND: Use search_specific for exact path matching
   - Best for queries like "users/alice" or "python guide"
   - Normalizes spaces to underscores

3. THIRD: Use search_folder_with_scoring for broader search
   - Scores documents by relevance (title, content, tags, category)
   - Only includes documents scoring above 0.3
   - Recurses into subfolders for general queries

4. FOURTH: If high confidence needed, use expand_backlinks
   - Finds documents that reference found documents
   - Useful for discovering related content

5. ALWAYS start with search_titles for the fastest results

IMPORTANT: Search queries may contain MULTIPLE topics.
For example, "Python decorators and React hooks" contains TWO topics:
- Python decorators (search for "decorator" or "python decorator")
- React hooks (search for "hook" or "react hook")

When you encounter multiple topics:
1. Identify each distinct topic in the query
2. Use search tools for EACH topic
3. Collect documents for ALL topics
4. Return ALL relevant documents from ALL topics

When you have found all relevant documents, respond with a JSON object:
{"paths": ["path/to/doc1.md", "path/to/doc2.md", ...]}

Always use the tools to explore the wiki. Do not guess document paths - verify them first."""


class SearchSpecificInput(BaseModel):
    query: str = Field(description="Search query for exact path matching")
    start_folder: str = Field(default="", description="Folder to start searching from")


class SearchSpecificOutput(BaseModel):
    paths: List[str] = Field(default_factory=list, description="Found document paths")


class SearchFolderWithScoringInput(BaseModel):
    folder: str = Field(default="", description="Folder path to search (empty for root)")
    query: str = Field(description="Search query for relevance scoring")
    specificity_level: str = Field(
        default="general",
        description="How specific the query is: very_specific, specific, general, very_general"
    )


class SearchFolderWithScoringOutput(BaseModel):
    paths: List[str] = Field(default_factory=list, description="Found document paths with scores")


class ExpandBacklinksInput(BaseModel):
    paths: List[str] = Field(description="Document paths to find backlinks for")


class ExpandBacklinksOutput(BaseModel):
    expanded_paths: List[str] = Field(default_factory=list, description="Documents that link to given paths")


def create_search_tools(
    wiki: WikiStore,
    logger: logging.Logger | None = None,
) -> list[ToolDefinition]:
    _logger = logger or logging.getLogger(__name__)

    def _relevance_score(
        doc: WikiDocument,
        query_lower: str,
    ) -> float:
        score = 0.0

        if query_lower in doc.title.lower():
            score += 0.5

        content_lower = doc.content.lower()
        if query_lower in content_lower:
            score += 0.3

        for tag in doc.tags:
            if query_lower in tag.lower():
                score += 0.2
                break

        if doc.category and query_lower in doc.category.lower():
            score += 0.1

        return min(score, 1.0)

    def search_specific(input: SearchSpecificInput) -> SearchSpecificOutput:
        paths: List[str] = []
        query_normalized = input.query.lower().replace(' ', '_')

        if '/' in input.query:
            test_path = input.query
            if not test_path.endswith('.md'):
                test_path = test_path + '.md'
            if wiki.document_exists(test_path):
                paths.append(test_path)
                _logger.debug(f"Found exact path: {test_path}")

        if input.start_folder:
            test_path = f"{input.start_folder}/{query_normalized}"
            if wiki.document_exists(test_path):
                paths.append(test_path)
                _logger.debug(f"Found in folder: {test_path}")

        if wiki.document_exists(query_normalized):
            paths.append(query_normalized)
            _logger.debug(f"Found normalized: {query_normalized}")

        return SearchSpecificOutput(paths=paths)

    def search_folder_with_scoring(input: SearchFolderWithScoringInput) -> SearchFolderWithScoringOutput:
        paths: List[str] = []
        query_lower = input.query.lower()

        def _search_folder_recursive(folder: str, depth: int = 0) -> None:
            if depth > 10:
                return
            try:
                content = wiki.list_folder(folder)
            except WikiStoreError:
                return

            for filename in content['files']:
                doc_path = f"{folder}/{filename}" if folder else filename
                try:
                    doc = wiki.read_document(doc_path)
                    score = _relevance_score(doc, query_lower)
                    if score > 0.3:
                        paths.append(doc_path)
                except WikiStoreError:
                    continue

            if input.specificity_level in ('general', 'very_general'):
                for subfolder in content['folders']:
                    subfolder_path = f"{folder}/{subfolder}" if folder else subfolder
                    _search_folder_recursive(subfolder_path, depth + 1)

        _search_folder_recursive(input.folder, 0)
        return SearchFolderWithScoringOutput(paths=paths)

    def expand_backlinks(input: ExpandBacklinksInput) -> ExpandBacklinksOutput:
        expanded: List[str] = []

        for path in input.paths:
            try:
                doc_path = wiki._doc_path(path)
                backlinks = wiki.backlinks.get_backlinks(doc_path)
                for backlink in backlinks:
                    if backlink not in expanded:
                        expanded.append(backlink)
            except Exception:
                continue

        return ExpandBacklinksOutput(expanded_paths=expanded)

    return [
        ToolDefinition(
            name="search_specific",
            description="Find documents by exact path matching. Normalizes spaces to underscores.",
            input_model=SearchSpecificInput,
            handler=search_specific,
        ),
        ToolDefinition(
            name="search_folder_with_scoring",
            description="Search folder with relevance scoring (title +0.5, content +0.3, tag +0.2, category +0.1). Recurses for general queries.",
            input_model=SearchFolderWithScoringInput,
            handler=search_folder_with_scoring,
        ),
        ToolDefinition(
            name="expand_backlinks",
            description="Find documents that link to the given paths via backlinks.",
            input_model=ExpandBacklinksInput,
            handler=expand_backlinks,
        ),
    ]


class SearcherWithAgentLoop:

    def __init__(self, wiki: WikiStore, agent_loop: AgentLoop, logger: Optional[logging.Logger] = None):
        self.wiki = wiki
        self.agent_loop = agent_loop
        self.logger = logger or logging.getLogger(__name__)

        self._register_tools()

    def _register_tools(self) -> None:
        for tool in create_wiki_tools(self.wiki):
            self.agent_loop.registry.register(tool)
        for tool in create_reasoning_tools(self.agent_loop.provider):
            self.agent_loop.registry.register(tool)
        for tool in create_search_tools(self.wiki, self.logger):
            self.agent_loop.registry.register(tool)

    def search(self, query: str | SearchQuery) -> SearchResult:
        if isinstance(query, str):
            search_query = SearchQuery(query=query)
        else:
            search_query = query

        self.logger.debug(f"Searching for: {search_query.query}")
        self.logger.debug(f"Search parameters: category={search_query.category_filter}, max_results={search_query.max_results}, mode={search_query.return_mode}")

        category_hint = ""
        if search_query.category_filter:
            category_hint = f"\nCategory filter: {search_query.category_filter} (restrict search to this category)"

        user_message = f"""Search the wiki for documents relevant to this query.

Query: {search_query.query}
Context: {search_query.context or 'General search'}
Max results: {search_query.max_results}{category_hint}

IMPORTANT: This query may contain MULTIPLE topics. Search for EACH topic separately and collect documents for ALL topics.

Explore the wiki structure, read documents to check relevance, and return the paths of the most relevant documents.
When you have found all relevant documents, respond with: {{"paths": ["path1", "path2", ...]}}"""

        self.agent_loop.reset()
        result = self.agent_loop.run(user_message=user_message)

        if result.truncated:
            self.logger.warning(f"Agent loop truncated after {result.steps} steps")

        paths = self._extract_paths_from_result(result.output)
        self.logger.debug(f"LLM found {len(paths)} documents: {paths}")

        # Deduplicate paths while preserving order
        seen: set[str] = set()
        unique_paths: List[str] = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)
        paths = unique_paths

        # Extract intent analysis from history if available
        query_analysis = self._extract_intent_from_history(result.history)

        search_result = SearchResult(
            paths=paths[:search_query.max_results],
            query_analysis=query_analysis,
        )

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

    def _extract_intent_from_history(self, history: list[dict[str, Any]]) -> IntentAnalysis | None:
        for msg in history:
            if msg.get("role") == "tool":
                try:
                    data = json.loads(msg.get("content", ""))
                    if isinstance(data, dict) and "information_type" in data and "specificity_level" in data:
                        return IntentAnalysis(**data)
                except (json.JSONDecodeError, Exception):
                    continue
        return None

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
