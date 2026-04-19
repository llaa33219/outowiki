"""Information search pipeline for OutoWiki."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..models.search import SearchQuery, SearchResult
from ..models.analysis import IntentAnalysis
from ..models.content import WikiDocument
from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from .agent import InternalAgent


class Searcher:
    """Information search pipeline.

    Processes search queries through intent analysis, document
    exploration, and result compilation.

    Pipeline:
        1. Analyze Intent: Understand what the user is looking for
        2. Explore: Navigate wiki structure to find relevant documents
        3. Return: Compile and format results

    Example:
        store = WikiStore("./wiki")
        agent = InternalAgent(provider)
        searcher = Searcher(store, agent)

        results = searcher.search("user preferences")
        print(results.paths)  # ['users/alice/preferences.md', ...]
    """

    def __init__(self, wiki: WikiStore, agent: InternalAgent, logger: Optional[logging.Logger] = None):
        """Initialize searcher.

        Args:
            wiki: Wiki store for document access
            agent: Internal agent for intent analysis
            logger: Optional logger for debug output
        """
        self.wiki = wiki
        self.agent = agent
        self.logger = logger or logging.getLogger(__name__)

    def search(self, query: str | SearchQuery) -> SearchResult:
        """Search the wiki for relevant documents."""
        if isinstance(query, str):
            search_query = SearchQuery(query=query)
        else:
            search_query = query

        self.logger.debug(f"Searching for: {search_query.query}")
        self.logger.debug(f"Search parameters: category={search_query.category_filter}, max_results={search_query.max_results}, mode={search_query.return_mode}")

        intent = self._analyze_intent(search_query)
        self.logger.debug(f"Intent analysis: type={intent.information_type}, specificity={intent.specificity_level}, start={intent.exploration_start}")

        paths = self._explore(intent, search_query)
        self.logger.debug(f"Found {len(paths)} documents: {paths}")

        result = self._return_results(paths, search_query, intent)
        self.logger.debug(f"Returning {len(result.paths)} results")
        return result

    def _analyze_intent(self, query: SearchQuery) -> IntentAnalysis:
        self.logger.debug("Analyzing search intent...")
        categories = self._get_categories()

        prompt = f"""Analyze this search query and determine the search strategy.

Query: {query.query}
Context: {query.context or 'General search'}
Available categories: {categories}

Determine:
1. information_type: What type of information is being sought? (user, tool, knowledge, history, agent)
2. specificity_level: How specific is the query? (very_specific, specific, general, very_general)
3. temporal_interest: Time relevance? (recent, all_time, specific_period)
4. exploration_start: Which category to start exploring? (folder path or 'root')
5. confidence_requirement: How confident must results be? (high, medium, low)

Respond with JSON matching IntentAnalysis schema."""

        intent = self.agent._call_with_schema(prompt, IntentAnalysis)
        self.logger.debug(f"Intent analysis completed: {intent}")
        return intent

    def _explore(self, intent: IntentAnalysis, query: SearchQuery) -> List[str]:
        self.logger.debug("Starting document exploration...")
        paths: List[str] = []

        start_folder = intent.exploration_start
        if start_folder == 'root':
            start_folder = ""

        if query.category_filter:
            start_folder = query.category_filter
            self.logger.debug(f"Using category filter: {start_folder}")

        self.logger.debug(f"Starting exploration from: {start_folder or 'root'}")

        if intent.specificity_level in ['very_specific', 'specific']:
            self.logger.debug("Performing specific search...")
            specific_paths = self._search_specific(query.query, start_folder)
            paths.extend(specific_paths)
            self.logger.debug(f"Specific search found {len(specific_paths)} documents")

        self.logger.debug("Performing folder search...")
        folder_paths = self._search_folder(start_folder, query.query, intent)
        paths.extend(folder_paths)
        self.logger.debug(f"Folder search found {len(folder_paths)} documents")

        if paths and intent.confidence_requirement == 'high':
            self.logger.debug("Expanding backlinks for high confidence...")
            backlink_paths = self._expand_backlinks(paths)
            paths.extend(backlink_paths)
            self.logger.debug(f"Backlink expansion added {len(backlink_paths)} documents")

        seen: set[str] = set()
        unique_paths: List[str] = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        self.logger.debug(f"Exploration completed: {len(unique_paths)} unique documents")
        return unique_paths[:query.max_results]

    def _search_specific(self, query: str, start_folder: str) -> List[str]:
        self.logger.debug(f"Performing specific search for: {query}")
        paths: List[str] = []
        query_normalized = query.lower().replace(' ', '_')

        if '/' in query:
            test_path = query
            if not test_path.endswith('.md'):
                test_path = test_path + '.md'
            if self.wiki.document_exists(test_path):
                paths.append(test_path)
                self.logger.debug(f"Found exact path: {test_path}")

        if start_folder:
            test_path = f"{start_folder}/{query_normalized}"
            if self.wiki.document_exists(test_path):
                paths.append(test_path)
                self.logger.debug(f"Found in folder: {test_path}")

        if self.wiki.document_exists(query_normalized):
            paths.append(query_normalized)
            self.logger.debug(f"Found normalized: {query_normalized}")

        self.logger.debug(f"Specific search found {len(paths)} documents")
        return paths

    def _search_folder(
        self,
        folder: str,
        query: str,
        intent: IntentAnalysis
    ) -> List[str]:
        self.logger.debug(f"Searching folder: {folder or 'root'}")
        paths: List[str] = []
        query_lower = query.lower()

        try:
            content = self.wiki.list_folder(folder)
            self.logger.debug(f"Folder contains {len(content['files'])} files, {len(content['folders'])} subfolders")

            for filename in content['files']:
                doc_path = f"{folder}/{filename}" if folder else filename

                try:
                    doc = self.wiki.read_document(doc_path)
                    score = self._relevance_score(doc, query_lower, intent)

                    if score > 0.3:
                        paths.append(doc_path)
                        self.logger.debug(f"Document {doc_path} has score {score:.2f} (included)")
                    else:
                        self.logger.debug(f"Document {doc_path} has score {score:.2f} (excluded)")
                except WikiStoreError:
                    self.logger.debug(f"Failed to read document: {doc_path}")
                    continue

            if intent.specificity_level in ['general', 'very_general']:
                self.logger.debug("Recursing into subfolders...")
                for subfolder in content['folders']:
                    subfolder_path = f"{folder}/{subfolder}" if folder else subfolder
                    subfolder_paths = self._search_folder(subfolder_path, query, intent)
                    paths.extend(subfolder_paths)
                    self.logger.debug(f"Subfolder {subfolder_path} found {len(subfolder_paths)} documents")

        except WikiStoreError:
            self.logger.debug(f"Folder not found: {folder}")

        self.logger.debug(f"Folder search found {len(paths)} documents")
        return paths

    def _relevance_score(
        self,
        doc: WikiDocument,
        query_lower: str,
        intent: IntentAnalysis
    ) -> float:
        score = 0.0

        if query_lower in doc.title.lower():
            score += 0.5
            self.logger.debug("Title match: +0.5")

        content_lower = doc.content.lower()
        if query_lower in content_lower:
            score += 0.3
            self.logger.debug("Content match: +0.3")

        for tag in doc.tags:
            if query_lower in tag.lower():
                score += 0.2
                self.logger.debug("Tag match: +0.2")
                break

        if query_lower in doc.category.lower():
            score += 0.1
            self.logger.debug("Category match: +0.1")

        if intent.information_type:
            type_keywords = {
                'user': ['user', 'preference', 'profile', 'person'],
                'tool': ['tool', 'function', 'method', 'api', 'usage'],
                'knowledge': ['learn', 'fact', 'concept', 'knowledge'],
                'history': ['history', 'session', 'conversation', 'log'],
                'agent': ['agent', 'self', 'identity', 'learning']
            }

            keywords = type_keywords.get(intent.information_type, [])
            for keyword in keywords:
                if keyword in content_lower or keyword in doc.title.lower():
                    score += 0.1
                    self.logger.debug(f"Type keyword match ({keyword}): +0.1")
                    break

        self.logger.debug(f"Total relevance score: {score:.2f}")
        return min(score, 1.0)

    def _expand_backlinks(self, paths: List[str]) -> List[str]:
        expanded: List[str] = []

        for path in paths:
            try:
                doc_path = self.wiki._doc_path(path)
                backlinks = self.wiki.backlinks.get_backlinks(doc_path)

                for backlink in backlinks:
                    if backlink not in expanded:
                        expanded.append(backlink)

            except Exception:
                continue

        return expanded

    def _return_results(
        self,
        paths: List[str],
        query: SearchQuery,
        intent: IntentAnalysis
    ) -> SearchResult:
        self.logger.debug(f"Returning results for {len(paths)} documents")
        result = SearchResult(paths=paths, query_analysis=intent)

        if query.return_mode in ['summary', 'full']:
            self.logger.debug("Generating summaries...")
            summaries: Dict[str, str] = {}
            for path in paths:
                try:
                    doc = self.wiki.read_document(path)
                    summary = self.agent.generate_summary(doc.content[:1000])
                    summaries[path] = summary
                    self.logger.debug(f"Summary for {path}: {summary[:50]}...")
                except Exception as e:
                    self.logger.error(f"Failed to generate summary for {path}: {e}")
                    summaries[path] = "Summary unavailable"
            result.summaries = summaries

        if query.return_mode == 'full':
            self.logger.debug("Loading full documents...")
            documents: Dict[str, WikiDocument] = {}
            for path in paths:
                try:
                    documents[path] = self.wiki.read_document(path)
                    self.logger.debug(f"Loaded full document: {path}")
                except WikiStoreError as e:
                    self.logger.error(f"Failed to load document {path}: {e}")
            result.documents = documents

        self.logger.debug(f"Results ready: {len(result.paths)} paths")
        return result

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
