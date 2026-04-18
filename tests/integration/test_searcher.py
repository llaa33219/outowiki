"""Integration tests for the Searcher pipeline."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from outowiki.core.store import WikiStore
from outowiki.models.search import SearchQuery, SearchResult
from outowiki.models.analysis import IntentAnalysis
from outowiki.models.content import WikiDocument
from outowiki.modules.agent import InternalAgent
from outowiki.modules.searcher import Searcher


def _write_doc(store: WikiStore, path: str, title: str, content: str, **kwargs):
    """Helper to write a document directly into the store."""
    doc = WikiDocument(
        path=path,
        title=title,
        content=content,
        frontmatter={},
        created=datetime.now(),
        modified=datetime.now(),
        tags=kwargs.get("tags", []),
        category=kwargs.get("category", ""),
        related=kwargs.get("related", []),
    )
    store.write_document(path, doc)
    return doc


@pytest.fixture
def mock_provider():
    """Sync mock provider with IntentAnalysis support."""
    provider = MagicMock()
    provider.complete.return_value = "Mock response"

    def mock_schema(prompt, schema, **kwargs):
        if schema is IntentAnalysis:
            return IntentAnalysis(
                information_type="knowledge",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="medium",
            )
        return schema()

    provider.complete_with_schema.side_effect = mock_schema
    return provider


@pytest.fixture
def agent(mock_provider):
    return InternalAgent(mock_provider)


@pytest.fixture
def wiki_store(tmp_path):
    wiki_dir = tmp_path / "test_wiki"
    wiki_dir.mkdir()
    return WikiStore(str(wiki_dir))


@pytest.fixture
def searcher(wiki_store, agent):
    return Searcher(wiki_store, agent)


# ── Intent analysis ─────────────────────────────────────────────────────


class TestAnalyzeIntent:
    """Tests for _analyze_intent."""

    def test_returns_intent_analysis(self, searcher, agent):
        """_analyze_intent returns IntentAnalysis from agent."""
        agent._call_with_schema = MagicMock(
            return_value=IntentAnalysis(
                information_type="user",
                specificity_level="specific",
                temporal_interest="recent",
                exploration_start="users",
                confidence_requirement="high",
            )
        )
        result = searcher._analyze_intent(SearchQuery(query="alice preferences"))
        assert result.information_type == "user"
        assert result.specificity_level == "specific"
        assert result.exploration_start == "users"

    def test_passes_query_in_prompt(self, searcher, agent):
        """_analyze_intent includes query text in prompt."""
        captured = {}

        def capture_call(prompt, schema, **kwargs):
            captured["prompt"] = prompt
            return IntentAnalysis(
                information_type="general",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low",
            )

        agent._call_with_schema = MagicMock(side_effect=capture_call)
        searcher._analyze_intent(SearchQuery(query="test query"))
        assert "test query" in captured["prompt"]

    def test_includes_context_when_provided(self, searcher, agent):
        """_analyze_intent includes context in prompt when provided."""
        captured = {}

        def capture_call(prompt, schema, **kwargs):
            captured["prompt"] = prompt
            return IntentAnalysis(
                information_type="general",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low",
            )

        agent._call_with_schema = MagicMock(side_effect=capture_call)
        searcher._analyze_intent(SearchQuery(query="test", context="some context"))
        assert "some context" in captured["prompt"]

    def test_includes_categories_in_prompt(self, searcher, agent, wiki_store):
        """_analyze_intent includes available categories in prompt."""
        wiki_store.create_folder("knowledge")
        wiki_store.create_folder("users")
        captured = {}

        def capture_call(prompt, schema, **kwargs):
            captured["prompt"] = prompt
            return IntentAnalysis(
                information_type="general",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low",
            )

        agent._call_with_schema = MagicMock(side_effect=capture_call)
        searcher._analyze_intent(SearchQuery(query="test"))
        assert "knowledge" in captured["prompt"]
        assert "users" in captured["prompt"]

    def test_delegates_to_agent_call_with_schema(self, searcher, agent):
        """_analyze_intent delegates to agent._call_with_schema with IntentAnalysis."""
        agent._call_with_schema = MagicMock(
            return_value=IntentAnalysis(
                information_type="knowledge",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low",
            )
        )
        searcher._analyze_intent(SearchQuery(query="test"))
        agent._call_with_schema.assert_called_once()
        call_args = agent._call_with_schema.call_args
        assert call_args[0][1] is IntentAnalysis


# ── Search specific ──────────────────────────────────────────────────────


class TestSearchSpecific:
    """Tests for _search_specific."""

    def test_finds_exact_path_with_slash(self, searcher, wiki_store):
        """_search_specific finds document when query contains '/'."""
        _write_doc(wiki_store, "users/alice/profile", "Alice Profile", "Content")
        results = searcher._search_specific("users/alice/profile", "")
        # The first branch appends path with .md extension
        assert any("users/alice/profile" in r for r in results)

    def test_finds_normalized_path_no_slash(self, searcher, wiki_store):
        """_search_specific normalizes spaces to underscores for lookup."""
        _write_doc(wiki_store, "my_document", "My Document", "Content")
        results = searcher._search_specific("my document", "")
        # query_normalized = "my_document", checked at root level
        assert "my_document" in results

    def test_finds_in_start_folder(self, searcher, wiki_store):
        """_search_specific checks within start_folder prefix."""
        wiki_store.create_folder("knowledge")
        _write_doc(wiki_store, "knowledge/python", "Python", "Content")
        results = searcher._search_specific("python", "knowledge")
        assert "knowledge/python" in results

    def test_returns_empty_for_missing(self, searcher, wiki_store):
        """_search_specific returns empty list for non-existent path."""
        results = searcher._search_specific("nonexistent/path", "")
        assert results == []

    def test_finds_at_root_level(self, searcher, wiki_store):
        """_search_specific finds document at root level without folder prefix."""
        _write_doc(wiki_store, "readme", "Readme", "Welcome to the wiki")
        results = searcher._search_specific("readme", "")
        assert "readme" in results

    def test_adds_md_extension_to_slash_path(self, searcher, wiki_store):
        """_search_specific appends .md to paths with '/' before checking."""
        _write_doc(wiki_store, "notes/meeting", "Meeting Notes", "Content")
        results = searcher._search_specific("notes/meeting", "")
        # First branch appends .md, third branch appends without .md
        assert any("notes/meeting" in r for r in results)
        assert len(results) >= 1


# ── Folder search ────────────────────────────────────────────────────────


class TestSearchFolder:
    """Tests for _search_folder."""

    def test_finds_matching_documents(self, searcher, wiki_store):
        """_search_folder finds documents whose title matches query."""
        _write_doc(wiki_store, "python_guide", "Python Guide", "Python programming basics")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="specific",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        results = searcher._search_folder("", "python", intent)
        assert "python_guide" in results

    def test_skips_low_relevance(self, searcher, wiki_store):
        """_search_folder skips documents with relevance score <= 0.3."""
        _write_doc(wiki_store, "unrelated_doc", "Unrelated", "Nothing relevant here")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="specific",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        results = searcher._search_folder("", "quantum physics", intent)
        assert "unrelated_doc" not in results

    def test_handles_nonexistent_folder(self, searcher, wiki_store):
        """_search_folder handles WikiStoreError for invalid folder gracefully."""
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        results = searcher._search_folder("nonexistent_folder", "test", intent)
        assert results == []

    def test_recurses_into_subfolders_for_general(self, searcher, wiki_store):
        """_search_folder recurses into subfolders for general queries."""
        wiki_store.create_folder("knowledge/programming")
        _write_doc(
            wiki_store,
            "knowledge/programming/guide",
            "Python Guide",
            "Python programming guide",
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        results = searcher._search_folder("", "python", intent)
        assert "knowledge/programming/guide" in results

    def test_does_not_recurse_for_specific(self, searcher, wiki_store):
        """_search_folder does NOT recurse for specific queries."""
        wiki_store.create_folder("knowledge/programming")
        _write_doc(
            wiki_store,
            "knowledge/programming/guide",
            "Python Guide",
            "Python programming guide",
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="specific",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        results = searcher._search_folder("", "python", intent)
        assert "knowledge/programming/guide" not in results


# ── Relevance scoring ────────────────────────────────────────────────────


class TestRelevanceScoring:
    """Tests for _relevance_score."""

    def test_title_match_adds_0_5(self, searcher):
        """Title match contributes 0.5 to score."""
        doc = WikiDocument(
            path="test",
            title="Python Guide",
            content="Some content",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category="",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "python", intent)
        assert score >= 0.5

    def test_content_match_adds_0_3(self, searcher):
        """Content match contributes 0.3 to score."""
        doc = WikiDocument(
            path="test",
            title="Guide",
            content="Python programming language",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category="",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "python", intent)
        assert score >= 0.3

    def test_tag_match_adds_0_2(self, searcher):
        """Tag match contributes 0.2 to score."""
        doc = WikiDocument(
            path="test",
            title="Guide",
            content="Some content",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=["python", "programming"],
            category="",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "python", intent)
        assert score >= 0.2

    def test_category_match_adds_0_1(self, searcher):
        """Category match contributes 0.1 to score."""
        doc = WikiDocument(
            path="test",
            title="Guide",
            content="Some content",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category="python",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "python", intent)
        assert score >= 0.1

    def test_info_type_keywords_add_0_1(self, searcher):
        """Information type keyword match in content adds 0.1 to score."""
        doc = WikiDocument(
            path="test",
            title="Data",
            content="User preferences for the application",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category="",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="user",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "application", intent)
        # "user" keyword from info_type matches "user" in content
        assert score >= 0.1

    def test_score_capped_at_one(self, searcher):
        """Score never exceeds 1.0 even with multiple matches."""
        doc = WikiDocument(
            path="python",
            title="Python Python Python",
            content="Python python python",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=["python"],
            category="python",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "python", intent)
        assert score <= 1.0

    def test_no_match_returns_zero(self, searcher):
        """Score is 0.0 when nothing matches."""
        doc = WikiDocument(
            path="test",
            title="Unrelated Title",
            content="Unrelated content about nothing",
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=["random"],
            category="misc",
            related=[],
        )
        intent = IntentAnalysis(
            information_type="tool",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        score = searcher._relevance_score(doc, "quantum entanglement", intent)
        assert score == 0.0


# ── Backlinks ────────────────────────────────────────────────────────────


class TestExpandBacklinks:
    """Tests for _expand_backlinks."""

    def test_finds_backlinked_documents(self, searcher, wiki_store):
        """_expand_backlinks finds documents that link to source paths."""
        _write_doc(wiki_store, "source_doc", "Source", "Source content")
        _write_doc(wiki_store, "linking_doc", "Linking", "See [[source_doc]] for details")
        results = searcher._expand_backlinks(["source_doc"])
        assert "linking_doc" in results

    def test_returns_empty_for_no_backlinks(self, searcher, wiki_store):
        """_expand_backlinks returns empty list when no backlinks exist."""
        _write_doc(wiki_store, "isolated_doc", "Isolated", "No links here")
        results = searcher._expand_backlinks(["isolated_doc"])
        assert results == []

    def test_handles_error_gracefully(self, searcher):
        """_expand_backlinks handles exceptions during lookup without raising."""
        results = searcher._expand_backlinks(["nonexistent"])
        assert isinstance(results, list)

    def test_deduplicates_within_expanded(self, searcher, wiki_store):
        """_expand_backlinks doesn't include duplicate backlinks."""
        _write_doc(wiki_store, "target", "Target", "Target content")
        _write_doc(wiki_store, "linker_a", "Linker A", "See [[target]]")
        _write_doc(wiki_store, "linker_b", "Linker B", "Also see [[target]] and [[target]]")
        results = searcher._expand_backlinks(["target"])
        # Each source should appear only once
        assert len(results) == len(set(results))

    def test_processes_multiple_paths(self, searcher, wiki_store):
        """_expand_backlinks processes multiple source paths."""
        _write_doc(wiki_store, "doc_a", "Doc A", "Content A")
        _write_doc(wiki_store, "doc_b", "Doc B", "Content B")
        _write_doc(wiki_store, "linker", "Linker", "See [[doc_a]] and [[doc_b]]")
        results = searcher._expand_backlinks(["doc_a", "doc_b"])
        assert "linker" in results


# ── Result compilation ───────────────────────────────────────────────────


class TestReturnResults:
    """Tests for _return_results."""

    def test_path_mode_returns_only_paths(self, searcher, wiki_store):
        """return_mode='path' returns paths without summaries or documents."""
        _write_doc(wiki_store, "test_doc", "Test", "Content")
        query = SearchQuery(query="test", return_mode="path")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        result = searcher._return_results(["test_doc"], query, intent)
        assert result.paths == ["test_doc"]
        assert result.summaries is None
        assert result.documents is None

    def test_summary_mode_generates_summaries(self, searcher, wiki_store, agent):
        """return_mode='summary' generates summaries via agent."""
        _write_doc(wiki_store, "test_doc", "Test", "Some content here")
        query = SearchQuery(query="test", return_mode="summary")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        result = searcher._return_results(["test_doc"], query, intent)
        assert result.summaries is not None
        assert "test_doc" in result.summaries
        assert result.summaries["test_doc"] == "Mock response"

    def test_full_mode_includes_documents(self, searcher, wiki_store):
        """return_mode='full' includes full WikiDocument objects."""
        _write_doc(wiki_store, "test_doc", "Test", "Full content here")
        query = SearchQuery(query="test", return_mode="full")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        result = searcher._return_results(["test_doc"], query, intent)
        assert result.documents is not None
        assert "test_doc" in result.documents
        assert isinstance(result.documents["test_doc"], WikiDocument)

    def test_handles_summary_error_gracefully(self, searcher, wiki_store, agent):
        """_return_results handles summary generation errors for missing docs."""
        query = SearchQuery(query="test", return_mode="summary")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        # Pass a path that doesn't exist - should get "Summary unavailable"
        result = searcher._return_results(["nonexistent_doc"], query, intent)
        assert result.summaries is not None
        assert result.summaries.get("nonexistent_doc") == "Summary unavailable"

    def test_handles_missing_doc_in_full_mode(self, searcher, wiki_store):
        """_return_results skips missing documents in full mode."""
        _write_doc(wiki_store, "existing_doc", "Existing", "Content")
        query = SearchQuery(query="test", return_mode="full")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        result = searcher._return_results(["existing_doc", "missing_doc"], query, intent)
        assert result.documents is not None
        assert "existing_doc" in result.documents
        assert "missing_doc" not in result.documents

    def test_empty_paths_returns_empty_result(self, searcher):
        """_return_results with empty paths returns empty SearchResult."""
        query = SearchQuery(query="test", return_mode="path")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        result = searcher._return_results([], query, intent)
        assert result.paths == []
        assert isinstance(result, SearchResult)


# ── Categories ───────────────────────────────────────────────────────────


class TestGetCategories:
    """Tests for _get_categories."""

    def test_lists_root_folders(self, searcher, wiki_store):
        """_get_categories lists root-level folders."""
        wiki_store.create_folder("knowledge")
        wiki_store.create_folder("users")
        categories = searcher._get_categories()
        assert "knowledge" in categories
        assert "users" in categories

    def test_includes_one_level_subfolders(self, searcher, wiki_store):
        """_get_categories includes one level of subfolders."""
        wiki_store.create_folder("knowledge/programming")
        wiki_store.create_folder("knowledge/science")
        categories = searcher._get_categories()
        assert "knowledge/programming" in categories
        assert "knowledge/science" in categories

    def test_handles_empty_wiki(self, searcher):
        """_get_categories returns empty list for empty wiki."""
        categories = searcher._get_categories()
        assert categories == []

    def test_excludes_files_from_categories(self, searcher, wiki_store):
        """_get_categories only returns folders, not files."""
        _write_doc(wiki_store, "standalone_doc", "Standalone", "Content")
        categories = searcher._get_categories()
        assert "standalone_doc" not in categories


# ── Explore phase ────────────────────────────────────────────────────────


class TestExplore:
    """Tests for _explore."""

    def test_deduplicates_results(self, searcher, wiki_store):
        """_explore deduplicates overlapping results from different search methods."""
        _write_doc(wiki_store, "python_guide", "Python Guide", "Python content")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="specific",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        query = SearchQuery(query="python_guide", max_results=10)
        results = searcher._explore(intent, query)
        # "python_guide" should appear at most once
        assert results.count("python_guide") <= 1

    def test_respects_max_results(self, searcher, wiki_store):
        """_explore limits results to max_results."""
        for i in range(10):
            _write_doc(wiki_store, f"python_{i}", f"Python {i}", f"Python content {i}")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        query = SearchQuery(query="python", max_results=3)
        results = searcher._explore(intent, query)
        assert len(results) <= 3

    def test_applies_category_filter(self, searcher, wiki_store):
        """_explore uses category_filter as start_folder override."""
        wiki_store.create_folder("knowledge")
        wiki_store.create_folder("users")
        _write_doc(wiki_store, "knowledge/python", "Python", "Python content")
        _write_doc(wiki_store, "users/alice", "Alice", "Alice content")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        query = SearchQuery(query="python", category_filter="knowledge")
        results = searcher._explore(intent, query)
        # Should find python in knowledge, not alice in users
        assert "knowledge/python" in results
        assert "users/alice" not in results

    def test_expands_backlinks_for_high_confidence(self, searcher, wiki_store):
        """_explore calls _expand_backlinks when confidence_requirement is 'high'."""
        _write_doc(wiki_store, "target_doc", "Target", "Target content")
        _write_doc(wiki_store, "linker_doc", "Linker", "See [[target_doc]]")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="specific",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="high",
        )
        query = SearchQuery(query="target_doc", max_results=10)
        results = searcher._explore(intent, query)
        # Should include both the found doc and its backlinks
        assert "target_doc" in results
        assert "linker_doc" in results

    def test_skips_backlinks_for_low_confidence(self, searcher, wiki_store):
        """_explore does NOT expand backlinks for low confidence."""
        _write_doc(wiki_store, "target_doc", "Target", "Target content")
        _write_doc(wiki_store, "linker_doc", "Linker", "See [[target_doc]]")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="specific",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        query = SearchQuery(query="target_doc", max_results=10)
        results = searcher._explore(intent, query)
        assert "target_doc" in results
        assert "linker_doc" not in results

    def test_root_exploration_start_searches_everywhere(self, searcher, wiki_store):
        """_explore with exploration_start='root' searches from wiki root."""
        wiki_store.create_folder("knowledge")
        _write_doc(wiki_store, "knowledge/guide", "Knowledge Guide", "Guide content")
        intent = IntentAnalysis(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="low",
        )
        query = SearchQuery(query="guide", max_results=10)
        results = searcher._explore(intent, query)
        assert "knowledge/guide" in results


# ── End-to-end search ────────────────────────────────────────────────────


class TestSearchPipeline:
    """End-to-end tests for search()."""

    def test_accepts_string_query(self, searcher):
        """search() accepts string query and converts to SearchQuery."""
        result = searcher.search("test query")
        assert isinstance(result, SearchResult)
        assert isinstance(result.paths, list)

    def test_returns_search_result(self, searcher, wiki_store):
        """search() returns SearchResult with paths."""
        _write_doc(wiki_store, "test_doc", "Test Document", "Test content")
        result = searcher.search("test")
        assert isinstance(result, SearchResult)
        assert isinstance(result.paths, list)

    def test_includes_intent_analysis(self, searcher):
        """search() includes IntentAnalysis in result."""
        result = searcher.search("test")
        assert result.query_analysis is not None
        assert isinstance(result.query_analysis, IntentAnalysis)

    def test_respects_max_results(self, searcher, wiki_store):
        """search() respects max_results parameter."""
        for i in range(15):
            _write_doc(wiki_store, f"doc_{i}", f"Document {i}", f"Content {i}")
        result = searcher.search(SearchQuery(query="document", max_results=5))
        assert len(result.paths) <= 5

    def test_with_category_filter(self, searcher, wiki_store):
        """search() applies category_filter when provided."""
        wiki_store.create_folder("knowledge")
        wiki_store.create_folder("users")
        _write_doc(wiki_store, "knowledge/python", "Python", "Python content")
        _write_doc(wiki_store, "users/alice", "Alice", "Alice content")
        result = searcher.search(SearchQuery(query="python", category_filter="knowledge"))
        assert isinstance(result, SearchResult)
        assert "knowledge/python" in result.paths
        assert "users/alice" not in result.paths

    def test_search_with_context(self, searcher, wiki_store):
        """search() passes context through to intent analysis."""
        searcher._analyze_intent = MagicMock(
            return_value=IntentAnalysis(
                information_type="knowledge",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low",
            )
        )
        searcher.search(SearchQuery(query="test", context="user context"))
        assert searcher._analyze_intent.called
        call_query = searcher._analyze_intent.call_args[0][0]
        assert call_query.context == "user context"
