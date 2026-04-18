"""Information search pipeline for OutoWiki."""

from __future__ import annotations

from typing import Dict, List

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

    def __init__(self, wiki: WikiStore, agent: InternalAgent):
        """Initialize searcher.

        Args:
            wiki: Wiki store for document access
            agent: Internal agent for intent analysis
        """
        self.wiki = wiki
        self.agent = agent

    def search(self, query: str | SearchQuery) -> SearchResult:
        """Search the wiki for relevant documents."""
        if isinstance(query, str):
            search_query = SearchQuery(query=query)
        else:
            search_query = query

        intent = self._analyze_intent(search_query)
        paths = self._explore(intent, search_query)
        return self._return_results(paths, search_query, intent)

    def _analyze_intent(self, query: SearchQuery) -> IntentAnalysis:
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

        return self.agent._call_with_schema(prompt, IntentAnalysis)

    def _explore(self, intent: IntentAnalysis, query: SearchQuery) -> List[str]:
        paths: List[str] = []

        start_folder = intent.exploration_start
        if start_folder == 'root':
            start_folder = ""

        if query.category_filter:
            start_folder = query.category_filter

        if intent.specificity_level in ['very_specific', 'specific']:
            paths.extend(self._search_specific(query.query, start_folder))

        paths.extend(self._search_folder(start_folder, query.query, intent))

        if paths and intent.confidence_requirement == 'high':
            paths.extend(self._expand_backlinks(paths))

        seen: set[str] = set()
        unique_paths: List[str] = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return unique_paths[:query.max_results]

    def _search_specific(self, query: str, start_folder: str) -> List[str]:
        paths: List[str] = []
        query_normalized = query.lower().replace(' ', '_')

        if '/' in query:
            test_path = query
            if not test_path.endswith('.md'):
                test_path = test_path + '.md'
            if self.wiki.document_exists(test_path):
                paths.append(test_path)

        if start_folder:
            test_path = f"{start_folder}/{query_normalized}"
            if self.wiki.document_exists(test_path):
                paths.append(test_path)

        if self.wiki.document_exists(query_normalized):
            paths.append(query_normalized)

        return paths

    def _search_folder(
        self,
        folder: str,
        query: str,
        intent: IntentAnalysis
    ) -> List[str]:
        paths: List[str] = []
        query_lower = query.lower()

        try:
            content = self.wiki.list_folder(folder)

            for filename in content['files']:
                doc_path = f"{folder}/{filename}" if folder else filename

                try:
                    doc = self.wiki.read_document(doc_path)
                    score = self._relevance_score(doc, query_lower, intent)

                    if score > 0.3:
                        paths.append(doc_path)
                except WikiStoreError:
                    continue

            if intent.specificity_level in ['general', 'very_general']:
                for subfolder in content['folders']:
                    subfolder_path = f"{folder}/{subfolder}" if folder else subfolder
                    paths.extend(self._search_folder(subfolder_path, query, intent))

        except WikiStoreError:
            pass

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

        content_lower = doc.content.lower()
        if query_lower in content_lower:
            score += 0.3

        for tag in doc.tags:
            if query_lower in tag.lower():
                score += 0.2
                break

        if query_lower in doc.category.lower():
            score += 0.1

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
                    break

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
        result = SearchResult(paths=paths, query_analysis=intent)

        if query.return_mode in ['summary', 'full']:
            summaries: Dict[str, str] = {}
            for path in paths:
                try:
                    doc = self.wiki.read_document(path)
                    summary = self.agent.generate_summary(doc.content[:1000])
                    summaries[path] = summary
                except Exception:
                    summaries[path] = "Summary unavailable"
            result.summaries = summaries

        if query.return_mode == 'full':
            documents: Dict[str, WikiDocument] = {}
            for path in paths:
                try:
                    documents[path] = self.wiki.read_document(path)
                except WikiStoreError:
                    pass
            result.documents = documents

        return result

    def _get_categories(self) -> List[str]:
        categories: List[str] = []
        try:
            root_content = self.wiki.list_folder("")
            for folder in root_content['folders']:
                categories.append(folder)
                try:
                    sub_content = self.wiki.list_folder(folder)
                    for subfolder in sub_content['folders']:
                        categories.append(f"{folder}/{subfolder}")
                except WikiStoreError:
                    pass
        except WikiStoreError:
            pass
        return categories
