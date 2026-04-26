"""Integration tests for the Searcher pipeline (AgentLoop version)."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from outowiki.core.store import WikiStore
from outowiki.models.search import SearchQuery, SearchResult
from outowiki.models.content import WikiDocument
from outowiki.modules.agent_loop import AgentLoop
from outowiki.modules.searcher_agent_loop import (
    SearcherWithAgentLoop,
    SYSTEM_PROMPT as SEARCHER_SYSTEM_PROMPT,
)
from outowiki.providers.base import ProviderResponse, ToolCall


def _write_doc(store: WikiStore, path: str, title: str, content: str, **kwargs):
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
    provider = MagicMock()
    provider.complete.return_value = "Mock response"

    def mock_schema(prompt, schema, **kwargs):
        if schema.__name__ == "SummaryGeneration":
            from outowiki.models.content import SummaryGeneration
            return SummaryGeneration(summary="Mock summary")
        if schema.__name__ == "DocumentGeneration":
            from outowiki.models.content import DocumentGeneration
            return DocumentGeneration(content="Mock response")
        return schema()

    provider.complete_with_schema.side_effect = mock_schema
    provider.chat_with_tools.return_value = ProviderResponse(
        content='{"paths": []}',
        tool_calls=None,
        finish_reason="stop",
    )
    return provider


@pytest.fixture
def wiki_store(tmp_path):
    wiki_dir = tmp_path / "test_wiki"
    wiki_dir.mkdir()
    return WikiStore(str(wiki_dir), init_default_folders=False)


@pytest.fixture
def agent_loop(mock_provider):
    return AgentLoop(
        provider=mock_provider,
        tools=[],
        system_prompt=SEARCHER_SYSTEM_PROMPT,
        max_iterations=5,
    )


@pytest.fixture
def searcher(wiki_store, agent_loop):
    return SearcherWithAgentLoop(wiki_store, agent_loop)


class TestSearchSpecific:
    def test_finds_exact_path_with_slash(self, searcher, wiki_store):
        _write_doc(wiki_store, "users/alice/profile", "Alice Profile", "Content")
        registry = searcher.agent_loop.registry
        result = registry.execute("search_specific", {
            "query": "users/alice/profile",
            "start_folder": "",
        })
        assert any("users/alice/profile" in r for r in result["paths"])

    def test_finds_normalized_path_no_slash(self, searcher, wiki_store):
        _write_doc(wiki_store, "my_document", "My Document", "Content")
        registry = searcher.agent_loop.registry
        result = registry.execute("search_specific", {
            "query": "my document",
            "start_folder": "",
        })
        assert "my_document" in result["paths"]

    def test_finds_in_start_folder(self, searcher, wiki_store):
        wiki_store.create_folder("knowledge")
        _write_doc(wiki_store, "knowledge/python", "Python", "Content")
        registry = searcher.agent_loop.registry
        result = registry.execute("search_specific", {
            "query": "python",
            "start_folder": "knowledge",
        })
        assert "knowledge/python" in result["paths"]

    def test_returns_empty_for_missing(self, searcher, wiki_store):
        registry = searcher.agent_loop.registry
        result = registry.execute("search_specific", {
            "query": "nonexistent/path",
            "start_folder": "",
        })
        assert result["paths"] == []

    def test_finds_at_root_level(self, searcher, wiki_store):
        _write_doc(wiki_store, "readme", "Readme", "Welcome to the wiki")
        registry = searcher.agent_loop.registry
        result = registry.execute("search_specific", {
            "query": "readme",
            "start_folder": "",
        })
        assert "readme" in result["paths"]


class TestSearchFolderWithScoring:
    def test_finds_matching_documents(self, searcher, wiki_store):
        _write_doc(wiki_store, "python_guide", "Python Guide", "Python programming basics")
        registry = searcher.agent_loop.registry
        result = registry.execute("search_folder_with_scoring", {
            "folder": "",
            "query": "python",
            "specificity_level": "specific",
        })
        assert "python_guide" in result["paths"]

    def test_skips_low_relevance(self, searcher, wiki_store):
        _write_doc(wiki_store, "unrelated_doc", "Unrelated", "Nothing relevant here")
        registry = searcher.agent_loop.registry
        result = registry.execute("search_folder_with_scoring", {
            "folder": "",
            "query": "quantum physics",
            "specificity_level": "specific",
        })
        assert "unrelated_doc" not in result["paths"]

    def test_handles_nonexistent_folder(self, searcher, wiki_store):
        registry = searcher.agent_loop.registry
        result = registry.execute("search_folder_with_scoring", {
            "folder": "nonexistent_folder",
            "query": "test",
            "specificity_level": "general",
        })
        assert result["paths"] == []

    def test_recurses_into_subfolders_for_general(self, searcher, wiki_store):
        wiki_store.create_folder("knowledge/programming")
        _write_doc(
            wiki_store,
            "knowledge/programming/guide",
            "Python Guide",
            "Python programming guide",
        )
        registry = searcher.agent_loop.registry
        result = registry.execute("search_folder_with_scoring", {
            "folder": "",
            "query": "python",
            "specificity_level": "general",
        })
        assert "knowledge/programming/guide" in result["paths"]

    def test_does_not_recurse_for_specific(self, searcher, wiki_store):
        wiki_store.create_folder("knowledge/programming")
        _write_doc(
            wiki_store,
            "knowledge/programming/guide",
            "Python Guide",
            "Python programming guide",
        )
        registry = searcher.agent_loop.registry
        result = registry.execute("search_folder_with_scoring", {
            "folder": "",
            "query": "python",
            "specificity_level": "specific",
        })
        assert "knowledge/programming/guide" not in result["paths"]


class TestExpandBacklinks:
    def test_finds_backlinked_documents(self, searcher, wiki_store):
        _write_doc(wiki_store, "source_doc", "Source", "Source content")
        _write_doc(wiki_store, "linking_doc", "Linking", "See [[source_doc]] for details")
        registry = searcher.agent_loop.registry
        result = registry.execute("expand_backlinks", {
            "paths": ["source_doc"],
        })
        assert "linking_doc" in result["expanded_paths"]

    def test_returns_empty_for_no_backlinks(self, searcher, wiki_store):
        _write_doc(wiki_store, "isolated_doc", "Isolated", "No links here")
        registry = searcher.agent_loop.registry
        result = registry.execute("expand_backlinks", {
            "paths": ["isolated_doc"],
        })
        assert result["expanded_paths"] == []

    def test_handles_error_gracefully(self, searcher):
        registry = searcher.agent_loop.registry
        result = registry.execute("expand_backlinks", {
            "paths": ["nonexistent"],
        })
        assert isinstance(result["expanded_paths"], list)

    def test_deduplicates_within_expanded(self, searcher, wiki_store):
        _write_doc(wiki_store, "target", "Target", "Target content")
        _write_doc(wiki_store, "linker_a", "Linker A", "See [[target]]")
        _write_doc(wiki_store, "linker_b", "Linker B", "Also see [[target]] and [[target]]")
        registry = searcher.agent_loop.registry
        result = registry.execute("expand_backlinks", {
            "paths": ["target"],
        })
        assert len(result["expanded_paths"]) == len(set(result["expanded_paths"]))

    def test_processes_multiple_paths(self, searcher, wiki_store):
        _write_doc(wiki_store, "doc_a", "Doc A", "Content A")
        _write_doc(wiki_store, "doc_b", "Doc B", "Content B")
        _write_doc(wiki_store, "linker", "Linker", "See [[doc_a]] and [[doc_b]]")
        registry = searcher.agent_loop.registry
        result = registry.execute("expand_backlinks", {
            "paths": ["doc_a", "doc_b"],
        })
        assert "linker" in result["expanded_paths"]


class TestGetCategories:
    def test_lists_root_folders(self, searcher, wiki_store):
        wiki_store.create_folder("knowledge")
        wiki_store.create_folder("users")
        categories = searcher.wiki.list_folder("")
        assert "knowledge" in categories["folders"]
        assert "users" in categories["folders"]

    def test_handles_empty_wiki(self, wiki_store):
        assert wiki_store.list_folder("")["folders"] == []


class TestSearchPipeline:
    def test_accepts_string_query(self, searcher, mock_provider):
        mock_provider.chat_with_tools.return_value = ProviderResponse(
            content='{"paths": []}',
            tool_calls=None,
            finish_reason="stop",
        )
        result = searcher.search("test query")
        assert isinstance(result, SearchResult)
        assert isinstance(result.paths, list)

    def test_returns_search_result(self, searcher, wiki_store, mock_provider):
        _write_doc(wiki_store, "test_doc", "Test Document", "Test content")

        call_count = 0
        def mock_chat(messages, tools, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ProviderResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_1",
                            name="search_folder_with_scoring",
                            arguments=json.dumps({
                                "folder": "",
                                "query": "test",
                                "specificity_level": "general",
                            }),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            return ProviderResponse(
                content='{"paths": ["test_doc"]}',
                tool_calls=None,
                finish_reason="stop",
            )

        mock_provider.chat_with_tools.side_effect = mock_chat
        result = searcher.search("test")
        assert isinstance(result, SearchResult)
        assert isinstance(result.paths, list)

    def test_respects_max_results(self, searcher, wiki_store, mock_provider):
        for i in range(15):
            _write_doc(wiki_store, f"doc_{i}", f"Document {i}", f"Content {i}")

        mock_provider.chat_with_tools.return_value = ProviderResponse(
            content=json.dumps({"paths": [f"doc_{i}" for i in range(15)]}),
            tool_calls=None,
            finish_reason="stop",
        )
        result = searcher.search(SearchQuery(query="document", max_results=5))
        assert len(result.paths) <= 5
