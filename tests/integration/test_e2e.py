"""End-to-end integration tests for OutoWiki."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from outowiki import OutoWiki, WikiConfig
from outowiki.providers.base import ProviderResponse, ToolCall


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.complete.return_value = "Mock response"

    def mock_schema(prompt, schema, **kwargs):
        return schema()

    provider.complete_with_schema.side_effect = mock_schema
    provider.chat_with_tools.return_value = ProviderResponse(
        content='{"success": true, "actions": [], "documents": []}',
        tool_calls=None,
        finish_reason="stop",
    )
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
                        name="execute_create_plan",
                        arguments=json.dumps({
                            "target_path": "test/test_document",
                            "title": "Test Document",
                            "content": "# Test Document\n\nTest content",
                            "category": "test",
                            "tags": ["test"],
                            "related": [],
                        }),
                    )
                ],
                finish_reason="tool_calls",
            )
        return ProviderResponse(
            content='{"success": true, "actions": ["Created: test/test_document"], "documents": ["test/test_document"]}',
            tool_calls=None,
            finish_reason="stop",
        )

    mock_provider.chat_with_tools.side_effect = mock_chat

    result = wiki.record("Test information")

    assert result.success
    assert wiki.wiki_path.joinpath("test/test_document.md").exists()


def test_search_returns_paths(wiki, mock_provider):
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
                            "query": "python",
                            "specificity_level": "general",
                        }),
                    )
                ],
                finish_reason="tool_calls",
            )
        return ProviderResponse(
            content='{"paths": ["knowledge/python"]}',
            tool_calls=None,
            finish_reason="stop",
        )

    mock_provider.chat_with_tools.side_effect = mock_chat

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
    assert "Updated content." in doc.content


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
