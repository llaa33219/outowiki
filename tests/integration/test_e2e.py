"""End-to-end integration tests for OutoWiki."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from outowiki import OutoWiki, WikiConfig
from outowiki.models.analysis import AnalysisResult, IntentAnalysis
from outowiki.models.plans import PlanType, CreatePlan
from outowiki.models.content import DocumentMetadata


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.complete.return_value = "Mock response"

    def mock_schema(prompt, schema, **kwargs):
        if schema is AnalysisResult:
            return AnalysisResult(
                information_type="conversation",
                key_topic="test",
                specific_content="Test content",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.9,
                importance_score=0.8,
                suggested_action=PlanType.CREATE,
                target_documents=[]
            )
        if schema is IntentAnalysis:
            return IntentAnalysis(
                information_type="knowledge",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="low"
            )
        return schema()

    provider.complete_with_schema.side_effect = mock_schema
    return provider


@pytest.fixture
def wiki_config(tmp_path):
    return WikiConfig(
        provider="openai",
        api_key="test-key",
        model="gpt-4",
        wiki_path=str(tmp_path / "test_wiki"),
        settings={"init_default_folders": False}
    )


@pytest.fixture
def wiki(wiki_config, mock_provider):
    with patch.object(OutoWiki, '_create_provider', return_value=mock_provider):
        return OutoWiki(wiki_config)


def test_record_creates_document(wiki, mock_provider):
    wiki._agent.plan = MagicMock(return_value=[
        CreatePlan(
            plan_type=PlanType.CREATE,
            target_path="test/document",
            reason="Test creation",
            content="Test content",
            metadata=DocumentMetadata(
                title="Test Document",
                category="test",
                tags=["test"]
            )
        )
    ])

    wiki._agent.generate_document = MagicMock(return_value="# Test Document\n\nTest content")

    result = wiki.record("Test information")

    assert result.success
    assert "Created: test/document" in result.actions_taken
    assert wiki.wiki_path.joinpath("test/document.md").exists()


def test_search_returns_paths(wiki):
    test_dir = wiki.wiki_path / "knowledge"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_doc = test_dir / "python.md"
    test_doc.write_text("""---
title: Python Programming
tags: [python, programming]
created: "2024-01-01T00:00:00"
modified: "2024-01-01T00:00:00"
category: knowledge
---
# Python

Python is a programming language.
""")

    results = wiki.search("python")

    assert len(results.paths) > 0
    assert any("python" in p for p in results.paths)


def test_get_document(wiki):
    test_dir = wiki.wiki_path / "users"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_doc = test_dir / "alice.md"
    test_doc.write_text("""---
title: Alice
tags: [user]
created: "2024-01-01T00:00:00"
modified: "2024-01-01T00:00:00"
category: users
---
# Alice

User profile for Alice.
""")

    doc = wiki.get_document("users/alice")

    assert doc.title == "Alice"
    assert "Alice" in doc.content
    assert "user" in doc.tags


def test_configure_updates_settings(wiki):
    wiki.configure(model="gpt-4-turbo", max_output_tokens=8000)

    assert wiki.config.model == "gpt-4-turbo"
    assert wiki.config.max_output_tokens == 8000


def test_list_categories(wiki):
    (wiki.wiki_path / "users").mkdir()
    (wiki.wiki_path / "knowledge").mkdir()
    (wiki.wiki_path / "tools").mkdir()

    categories = wiki.list_categories()

    assert set(categories) == {"users", "knowledge", "tools"}


def test_list_documents(wiki):
    test_dir = wiki.wiki_path / "users"
    test_dir.mkdir()
    (test_dir / "alice.md").write_text("# Alice")
    (test_dir / "bob.md").write_text("# Bob")

    docs = wiki.list_documents("users")

    assert set(docs) == {"alice", "bob"}


def test_update_document(wiki):
    test_dir = wiki.wiki_path / "notes"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "note1.md").write_text("""---
title: Note 1
tags: []
created: "2024-01-01T00:00:00"
modified: "2024-01-01T00:00:00"
category: notes
---
# Note 1

Original content.
""")

    wiki.update_document("notes/note1", "# Note 1\n\nUpdated content.")

    doc = wiki.get_document("notes/note1")
    assert "Updated content" in doc.content


def test_delete_document(wiki):
    test_dir = wiki.wiki_path / "temp"
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "deleteme.md").write_text("""---
title: Delete Me
tags: []
created: "2024-01-01T00:00:00"
modified: "2024-01-01T00:00:00"
category: temp
---
# Delete Me
""")

    wiki.delete_document("temp/deleteme")

    assert not wiki.wiki_path.joinpath("temp/deleteme.md").exists()


def test_wiki_path_property(wiki, wiki_config):
    assert wiki.wiki_path.exists()
    assert wiki.wiki_path.is_dir()


def test_provider_property(wiki, mock_provider):
    assert wiki.provider is mock_provider
