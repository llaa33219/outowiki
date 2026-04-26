"""Integration tests for the Recorder pipeline (AgentLoop version)."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from outowiki.core.store import WikiStore
from outowiki.models.content import WikiDocument
from outowiki.modules.agent_loop import AgentLoop
from outowiki.modules.recorder_agent_loop import (
    RecorderWithAgentLoop,
    SYSTEM_PROMPT as RECORDER_SYSTEM_PROMPT,
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
        return schema()

    provider.complete_with_schema.side_effect = mock_schema
    provider.chat_with_tools.return_value = ProviderResponse(
        content='{"success": true, "actions": [], "documents": []}',
        tool_calls=None,
        finish_reason="stop",
    )
    return provider


@pytest.fixture
def wiki_store(tmp_path):
    wiki_dir = tmp_path / "test_wiki"
    wiki_dir.mkdir()
    return WikiStore(str(wiki_dir))


@pytest.fixture
def agent_loop(mock_provider):
    return AgentLoop(
        provider=mock_provider,
        tools=[],
        system_prompt=RECORDER_SYSTEM_PROMPT,
        max_iterations=5,
    )


@pytest.fixture
def recorder(wiki_store, agent_loop):
    return RecorderWithAgentLoop(wiki_store, agent_loop)


class TestExecuteCreate:
    def test_execute_create_plan(self, recorder, wiki_store):
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_create_plan", {
            "target_path": "test/test_doc",
            "title": "Test Doc",
            "content": "# Test Doc\n\nGenerated content",
            "category": "test",
            "tags": ["test"],
            "related": [],
        })
        assert result["success"]
        assert wiki_store.document_exists("test/test_doc")
        doc = wiki_store.read_document("test/test_doc")
        assert doc.title == "Test Doc"
        assert "Generated content" in doc.content
        assert doc.category == "test"
        assert "test" in doc.tags
        versions = wiki_store.get_versions("test/test_doc")
        assert len(versions) >= 1

    def test_execute_create_with_frontmatter_stripping(self, recorder, wiki_store):
        content_with_frontmatter = """---
title: Wrong Title
created: 2020-01-01T00:00:00
modified: 2020-01-01T00:00:00
---

# Correct Title

This is the actual body content.
"""
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_create_plan", {
            "target_path": "test/correct_title",
            "title": "Correct Title",
            "content": content_with_frontmatter,
            "category": "test",
            "tags": ["test"],
            "related": [],
        })
        assert result["success"]
        doc = wiki_store.read_document("test/correct_title")
        assert "---" not in doc.content
        assert "Wrong Title" not in doc.content
        assert "This is the actual body content." in doc.content
        assert doc.title == "Correct Title"


class TestExecuteModify:
    def test_execute_modify_append(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "notes/append",
            "Append Test",
            "# Append Test\n\nOriginal content.",
        )
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_modify_plan", {
            "target_path": "notes/append",
            "modifications": [
                {"operation": "append", "content": "Appended content."},
            ],
        })
        assert result["success"]
        doc = wiki_store.read_document("notes/append")
        assert "Original content." in doc.content
        assert "Appended content." in doc.content

    def test_execute_modify_prepend(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "notes/prepend",
            "Prepend Test",
            "# Prepend Test\n\nOriginal body.",
        )
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_modify_plan", {
            "target_path": "notes/prepend",
            "modifications": [
                {"operation": "prepend", "content": "Prepended intro."},
            ],
        })
        assert result["success"]
        doc = wiki_store.read_document("notes/prepend")
        body = doc.content
        assert body.index("Prepended intro.") < body.index("Original body.")

    def test_execute_modify_replace_section(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "notes/sections",
            "Sectioned Doc",
            "# Sectioned Doc\n\n## Intro\n\nOld intro text.\n\n## Details\n\nDetails here.\n\n## Summary\n\nOld summary.",
        )
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_modify_plan", {
            "target_path": "notes/sections",
            "modifications": [
                {
                    "section": "Intro",
                    "operation": "replace_section",
                    "content": "New intro text.",
                },
            ],
        })
        assert result["success"]
        doc = wiki_store.read_document("notes/sections")
        assert "New intro text." in doc.content
        assert "Old intro text." not in doc.content
        assert "Details here." in doc.content
        assert "Old summary." in doc.content

    def test_execute_modify_strips_frontmatter(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "notes/modify_fm",
            "Modify FM Test",
            "# Modify FM Test\n\nOriginal content.",
        )
        mod_content = """---
title: Wrong
---

New appended content.
"""
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_modify_plan", {
            "target_path": "notes/modify_fm",
            "modifications": [
                {"operation": "append", "content": mod_content},
            ],
        })
        assert result["success"]
        doc = wiki_store.read_document("notes/modify_fm")
        assert "Original content." in doc.content
        assert "New appended content." in doc.content
        assert doc.content.count("---") == 0

    def test_execute_modify_nonexistent_raises(self, recorder, wiki_store):
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_modify_plan", {
            "target_path": "notes/nonexistent",
            "modifications": [
                {"operation": "append", "content": "Some content"},
            ],
        })
        assert "error" in result


class TestExecuteMerge:
    def test_execute_merge(self, recorder, wiki_store):
        _write_doc(wiki_store, "src/a", "Doc A", "# Doc A\n\nContent A", category="src")
        _write_doc(wiki_store, "src/b", "Doc B", "# Doc B\n\nContent B", category="src")
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_merge_plan", {
            "target_path": "src/merged",
            "source_paths": ["src/a", "src/b"],
            "merged_content": "# Merged\n\nContent A\n\nContent B",
            "redirect_sources": True,
        })
        assert result["success"]
        assert wiki_store.document_exists("src/merged")
        merged = wiki_store.read_document("src/merged")
        assert "Content A" in merged.content
        assert not wiki_store.document_exists("src/a")
        assert not wiki_store.document_exists("src/b")

    def test_execute_merge_strips_frontmatter(self, recorder, wiki_store):
        _write_doc(wiki_store, "src/m_a", "Doc A", "# Doc A\n\nContent A", category="src")
        _write_doc(wiki_store, "src/m_b", "Doc B", "# Doc B\n\nContent B", category="src")
        merged_with_fm = """---
title: Merged Wrong
---

# Merged Correct

Content A and Content B merged.
"""
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_merge_plan", {
            "target_path": "src/merged_fm",
            "source_paths": ["src/m_a", "src/m_b"],
            "merged_content": merged_with_fm,
            "redirect_sources": False,
        })
        assert result["success"]
        doc = wiki_store.read_document("src/merged_fm")
        assert "Merged Wrong" not in doc.content
        assert "Content A and Content B merged." in doc.content
        assert doc.content.count("---") == 0


class TestExecuteSplit:
    def test_execute_split(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "topics/big",
            "Big Topic",
            "# Big Topic\n\nOverview text.\n\n## Sub A\n\nSub A details.\n\n## Sub B\n\nSub B details.",
            category="topics",
            tags=["big"],
        )
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_split_plan", {
            "target_path": "topics/big",
            "sections_to_split": [
                {"new_path": "topics/sub_a", "content": "# Sub A\n\nSub A details."},
                {"new_path": "topics/sub_b", "content": "# Sub B\n\nSub B details."},
            ],
            "summary_for_main": "# Big Topic\n\nSee [[topics/sub_a]] and [[topics/sub_b]].",
        })
        assert result["success"]
        assert "topics/sub_a" in result.get("new_paths", [])
        assert "topics/sub_b" in result.get("new_paths", [])
        assert wiki_store.document_exists("topics/sub_a")
        assert wiki_store.document_exists("topics/sub_b")
        main = wiki_store.read_document("topics/big")
        assert "See" in main.content or "sub_a" in main.related

    def test_execute_split_strips_frontmatter(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "topics/split_fm",
            "Split FM",
            "# Split FM\n\nIntro.\n\n## Sec A\n\nA.\n\n## Sec B\n\nB.",
            category="topics",
        )
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_split_plan", {
            "target_path": "topics/split_fm",
            "sections_to_split": [
                {"new_path": "topics/sec_a_fm", "content": "---\ntitle: Wrong A\n---\n# Sec A\n\nBody A."},
                {"new_path": "topics/sec_b_fm", "content": "---\ntitle: Wrong B\n---\n# Sec B\n\nBody B."},
            ],
            "summary_for_main": "---\ntitle: Wrong Summary\n---\n# Split FM\n\nSee sub-docs.",
        })
        assert result["success"]
        sec_a = wiki_store.read_document("topics/sec_a_fm")
        assert "Wrong A" not in sec_a.content
        assert "Body A." in sec_a.content
        sec_b = wiki_store.read_document("topics/sec_b_fm")
        assert "Wrong B" not in sec_b.content
        assert "Body B." in sec_b.content
        main = wiki_store.read_document("topics/split_fm")
        assert "Wrong Summary" not in main.content
        assert "See sub-docs." in main.content


class TestExecuteDelete:
    def test_execute_delete(self, recorder, wiki_store):
        _write_doc(wiki_store, "temp/delete_me", "Delete Me", "Content to delete")
        registry = recorder.agent_loop.registry
        result = registry.execute("execute_delete_plan", {
            "target_path": "temp/delete_me",
            "remove_backlinks": True,
        })
        assert result["success"]
        assert not wiki_store.document_exists("temp/delete_me")


class TestHistoryIntegration:
    def test_record_saves_version(self, recorder, wiki_store, mock_provider):
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
                                "target_path": "notes/versioned_note",
                                "title": "Versioned Note",
                                "content": "# Versioned Note\n\nVersion content",
                                "category": "notes",
                                "tags": ["version"],
                                "related": [],
                            }),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            return ProviderResponse(
                content='{"success": true, "actions": ["Created: notes/versioned_note"], "documents": ["notes/versioned_note"]}',
                tool_calls=None,
                finish_reason="stop",
            )

        mock_provider.chat_with_tools.side_effect = mock_chat

        result = recorder.record("Version test info")
        assert result.success

        versions = wiki_store.get_versions("notes/versioned_note")
        assert len(versions) >= 1
        assert versions[0].created_by_operation.value == "create"

    def test_history_preserved_on_split(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "topics/split_me",
            "Split Source",
            "# Split Source\n\nIntro.\n\n## Section A\n\nA content.\n\n## Section B\n\nB content.",
            category="topics",
            tags=["split"],
        )
        registry = recorder.agent_loop.registry
        registry.execute("execute_split_plan", {
            "target_path": "topics/split_me",
            "sections_to_split": [
                {"new_path": "topics/section_a", "content": "# Section A\n\nA content."},
                {"new_path": "topics/section_b", "content": "# Section B\n\nB content."},
            ],
            "summary_for_main": "# Split Source\n\nSplit into sub-documents.",
        })

        source_versions = wiki_store.get_versions("topics/split_me")
        assert any(v.created_by_operation.value == "split" for v in source_versions)

        a_versions = wiki_store.get_versions("topics/section_a")
        assert len(a_versions) >= 1
        assert a_versions[0].created_by_operation.value == "split"

        b_versions = wiki_store.get_versions("topics/section_b")
        assert len(b_versions) >= 1
        assert b_versions[0].created_by_operation.value == "split"

    def test_rollback_after_modify(self, recorder, wiki_store):
        _write_doc(
            wiki_store,
            "notes/rollback",
            "Rollback Test",
            "# Rollback Test\n\nOriginal content.",
        )
        wiki_store.save_version("notes/rollback", "create")

        doc = wiki_store.read_document("notes/rollback")
        doc.content += "\n\nModified content."
        wiki_store.write_document("notes/rollback", doc)
        wiki_store.save_version("notes/rollback", "modify")

        versions = wiki_store.get_versions("notes/rollback")
        assert len(versions) == 2

        rollback_result = wiki_store.rollback_to_version("notes/rollback", 1)
        assert rollback_result.success
        assert rollback_result.version_restored == 1

        restored = wiki_store.read_document("notes/rollback")
        assert "Original content." in restored.content


class TestRecordPipeline:
    def test_record_creates_document(self, recorder, wiki_store, mock_provider):
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
                                "target_path": "users/user_preferences",
                                "title": "User Preferences",
                                "content": "# User Preferences\n\nUser prefers Python for development.",
                                "category": "users",
                                "tags": ["preferences", "python"],
                                "related": [],
                            }),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            return ProviderResponse(
                content='{"success": true, "actions": ["Created: users/user_preferences"], "documents": ["users/user_preferences"]}',
                tool_calls=None,
                finish_reason="stop",
            )

        mock_provider.chat_with_tools.side_effect = mock_chat

        result = recorder.record("User prefers Python for development")

        assert result.success
        assert wiki_store.document_exists("users/user_preferences")

    def test_record_modifies_document(self, recorder, wiki_store, mock_provider):
        _write_doc(
            wiki_store,
            "notes/log",
            "Activity Log",
            "# Activity Log\n\nPrevious entries.",
        )
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
                            name="execute_modify_plan",
                            arguments=json.dumps({
                                "target_path": "notes/log",
                                "modifications": [
                                    {"operation": "append", "content": "New activity entry."},
                                ],
                            }),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            return ProviderResponse(
                content='{"success": true, "actions": ["Modified: notes/log"], "documents": ["notes/log"]}',
                tool_calls=None,
                finish_reason="stop",
            )

        mock_provider.chat_with_tools.side_effect = mock_chat

        result = recorder.record("New activity happened")
        assert result.success
        doc = wiki_store.read_document("notes/log")
        assert "New activity entry." in doc.content

    def test_record_handles_error(self, recorder, mock_provider):
        mock_provider.chat_with_tools.side_effect = RuntimeError("LLM unavailable")

        result = recorder.record("Something")

        assert not result.success
        assert result.error is not None
        assert result.actions_taken == []
        assert result.documents_affected == []

    def test_record_with_dict_content(self, recorder, wiki_store, mock_provider):
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
                                "target_path": "config/settings",
                                "title": "Settings",
                                "content": "# Settings\n\nConfig data",
                                "category": "config",
                                "tags": ["config"],
                                "related": [],
                            }),
                        )
                    ],
                    finish_reason="tool_calls",
                )
            return ProviderResponse(
                content='{"success": true, "actions": ["Created: config/settings"], "documents": ["config/settings"]}',
                tool_calls=None,
                finish_reason="stop",
            )

        mock_provider.chat_with_tools.side_effect = mock_chat

        result = recorder.record(
            {"content": "Config data", "type": "structured", "context": {"env": "prod"}}
        )

        assert result.success
