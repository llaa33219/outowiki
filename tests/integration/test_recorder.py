"""Integration tests for the Recorder pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from outowiki.core.store import WikiStore
from outowiki.models.analysis import AnalysisResult
from outowiki.models.content import DocumentMetadata, WikiDocument
from outowiki.models.plans import (
    CreatePlan,
    MergePlan,
    ModifyPlan,
    PlanType,
    SplitPlan,
)
from outowiki.modules.agent import InternalAgent
from outowiki.modules.recorder import Recorder, RecordResult


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_provider():
    """Sync mock provider matching test_e2e.py pattern."""
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
                target_documents=[],
            )
        return schema()

    provider.complete_with_schema.side_effect = mock_schema
    return provider


@pytest.fixture
def wiki_store(tmp_path):
    """Isolated WikiStore using tmp_path."""
    wiki_dir = tmp_path / "test_wiki"
    wiki_dir.mkdir()
    return WikiStore(str(wiki_dir))


@pytest.fixture
def agent(mock_provider):
    """InternalAgent backed by mock provider."""
    return InternalAgent(mock_provider)


@pytest.fixture
def recorder(wiki_store, agent):
    """Recorder with real store and mock-backed agent."""
    return Recorder(wiki_store, agent)


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


# ── Analyze phase ─────────────────────────────────────────────────────


class TestAnalyze:
    def test_analyze_conversation(self, recorder, agent):
        """_analyze passes content and content_type to agent.analyze."""
        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="conversation",
                key_topic="testing",
                specific_content="Test info",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.9,
                importance_score=0.8,
                suggested_action=PlanType.CREATE,
                target_documents=[],
            )
        )

        result = recorder._analyze("Some conversation text", "conversation", {})

        assert result.information_type == "conversation"
        assert result.key_topic == "testing"
        agent.analyze.assert_called_once()
        call_args = agent.analyze.call_args
        assert call_args[0][0] == "Some conversation text"
        assert call_args[0][1] == "conversation"

    def test_analyze_with_context(self, recorder, agent):
        """_analyze enriches context with categories and recent_docs."""
        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="agent_internal",
                key_topic="ctx",
                specific_content="Context test",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.8,
                importance_score=0.7,
                suggested_action=PlanType.CREATE,
                target_documents=[],
            )
        )

        recorder._analyze("content", "agent_internal", {"user_context": "value"})

        context_passed = agent.analyze.call_args[0][2]
        assert "user_context" in context_passed
        assert "categories" in context_passed
        assert "recent_docs" in context_passed

    def test_analyze_with_recent_docs(self, recorder, wiki_store, agent):
        """_analyze includes recently modified documents in context."""
        _write_doc(wiki_store, "notes/recent1", "Recent1", "Recent content 1")
        _write_doc(wiki_store, "notes/recent2", "Recent2", "Recent content 2")

        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="external",
                key_topic="recent",
                specific_content="Recent doc test",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.8,
                importance_score=0.7,
                suggested_action=PlanType.CREATE,
                target_documents=[],
            )
        )

        recorder._analyze("check recent", "external", {})

        context_passed = agent.analyze.call_args[0][2]
        recent = context_passed["recent_docs"]
        assert len(recent) >= 2
        assert any("recent1" in d for d in recent)
        assert any("recent2" in d for d in recent)


# ── Plan phase ────────────────────────────────────────────────────────


class TestPlan:
    def test_plan_create_new_doc(self, recorder, agent):
        """_plan calls agent.plan for a new document (no existing content)."""
        analysis = AnalysisResult(
            information_type="conversation",
            key_topic="new_topic",
            specific_content="Brand new info",
            existing_relations=[],
            temporal_range="timeless",
            confidence_score=0.9,
            importance_score=0.8,
            suggested_action=PlanType.CREATE,
            target_documents=["topics/new_thing"],
        )

        expected_plan = CreatePlan(
            plan_type=PlanType.CREATE,
            target_path="topics/new_thing",
            reason="New topic",
            content="New thing content",
            metadata=DocumentMetadata(
                title="New Thing",
                category="topics",
                tags=["new"],
            ),
        )
        agent.plan = MagicMock(return_value=[expected_plan])

        plans = recorder._plan(analysis)

        assert len(plans) == 1
        assert plans[0].plan_type == PlanType.CREATE
        assert plans[0].target_path == "topics/new_thing"
        # affected_docs should be empty since doc doesn't exist
        agent.plan.assert_called_once_with(analysis, {})

    def test_plan_modify_existing(self, recorder, wiki_store, agent):
        """_plan includes existing document content in affected_docs."""
        _write_doc(
            wiki_store,
            "notes/existing",
            "Existing Note",
            "# Existing Note\n\nSome existing content here.",
        )

        analysis = AnalysisResult(
            information_type="conversation",
            key_topic="existing",
            specific_content="Update existing",
            existing_relations=[],
            temporal_range="timeless",
            confidence_score=0.9,
            importance_score=0.8,
            suggested_action=PlanType.MODIFY,
            target_documents=["notes/existing"],
        )

        agent.plan = MagicMock(return_value=[])

        recorder._plan(analysis)

        affected_docs = agent.plan.call_args[0][1]
        assert "notes/existing" in affected_docs
        assert "Some existing content" in affected_docs["notes/existing"]

    def test_plan_with_affected_docs(self, recorder, wiki_store, agent):
        """_plan truncates affected doc content to 500 chars."""
        long_content = "x" * 1000
        _write_doc(
            wiki_store,
            "notes/long",
            "Long Doc",
            f"# Long Doc\n\n{long_content}",
        )

        analysis = AnalysisResult(
            information_type="conversation",
            key_topic="long",
            specific_content="Long content",
            existing_relations=[],
            temporal_range="timeless",
            confidence_score=0.9,
            importance_score=0.8,
            suggested_action=PlanType.MODIFY,
            target_documents=["notes/long"],
        )

        agent.plan = MagicMock(return_value=[])

        recorder._plan(analysis)

        affected_docs = agent.plan.call_args[0][1]
        assert len(affected_docs["notes/long"]) <= 500


# ── Execute phase ─────────────────────────────────────────────────────


class TestExecute:
    def test_execute_create(self, recorder, wiki_store, agent):
        """_execute_create writes a document and saves a version."""
        agent.generate_document = MagicMock(return_value="# Test Doc\n\nGenerated content")

        plan = CreatePlan(
            plan_type=PlanType.CREATE,
            target_path="test/new_doc",
            reason="Test create",
            content="Raw info",
            metadata=DocumentMetadata(
                title="Test Doc",
                category="test",
                tags=["test"],
            ),
        )

        recorder._execute_create(plan)

        assert wiki_store.document_exists("test/new_doc")
        doc = wiki_store.read_document("test/new_doc")
        assert doc.title == "Test Doc"
        assert "Generated content" in doc.content
        assert doc.category == "test"
        assert "test" in doc.tags
        # Version should be saved
        versions = wiki_store.get_versions("test/new_doc")
        assert len(versions) >= 1

    def test_execute_modify_append(self, recorder, wiki_store):
        """_execute_modify appends content to existing document."""
        _write_doc(
            wiki_store,
            "notes/append",
            "Append Test",
            "# Append Test\n\nOriginal content.",
        )

        plan = ModifyPlan(
            plan_type=PlanType.MODIFY,
            target_path="notes/append",
            reason="Append new info",
            modifications=[
                {"operation": "append", "content": "Appended content."},
            ],
        )

        recorder._execute_modify(plan)

        doc = wiki_store.read_document("notes/append")
        assert "Original content." in doc.content
        assert "Appended content." in doc.content

    def test_execute_modify_prepend(self, recorder, wiki_store):
        """_execute_modify prepends content to existing document."""
        _write_doc(
            wiki_store,
            "notes/prepend",
            "Prepend Test",
            "# Prepend Test\n\nOriginal body.",
        )

        plan = ModifyPlan(
            plan_type=PlanType.MODIFY,
            target_path="notes/prepend",
            reason="Prepend info",
            modifications=[
                {"operation": "prepend", "content": "Prepended intro."},
            ],
        )

        recorder._execute_modify(plan)

        doc = wiki_store.read_document("notes/prepend")
        body = doc.content
        assert body.index("Prepended intro.") < body.index("Original body.")

    def test_execute_modify_replace_section(self, recorder, wiki_store):
        """_execute_modify replaces content under a specific section heading."""
        _write_doc(
            wiki_store,
            "notes/sections",
            "Sectioned Doc",
            "# Sectioned Doc\n\n## Intro\n\nOld intro text.\n\n## Details\n\nDetails here.\n\n## Summary\n\nOld summary.",
        )

        plan = ModifyPlan(
            plan_type=PlanType.MODIFY,
            target_path="notes/sections",
            reason="Update intro section",
            modifications=[
                {
                    "section": "Intro",
                    "operation": "replace_section",
                    "content": "New intro text.",
                },
            ],
        )

        recorder._execute_modify(plan)

        doc = wiki_store.read_document("notes/sections")
        assert "New intro text." in doc.content
        assert "Old intro text." not in doc.content
        # Other sections should remain untouched
        assert "Details here." in doc.content
        assert "Old summary." in doc.content

    def test_execute_merge(self, recorder, wiki_store):
        """_execute_merge creates merged doc and deletes sources."""
        _write_doc(
            wiki_store, "src/a", "Doc A", "# Doc A\n\nContent A", category="src"
        )
        _write_doc(
            wiki_store, "src/b", "Doc B", "# Doc B\n\nContent B", category="src"
        )

        plan = MergePlan(
            plan_type=PlanType.MERGE,
            target_path="src/merged",
            reason="Combine A and B",
            source_paths=["src/a", "src/b"],
            merged_content="# Merged\n\nContent A\n\nContent B",
            redirect_sources=True,
        )

        result = recorder._execute_merge(plan)

        assert "src/a" in result
        assert "src/b" in result
        assert "src/merged" in result
        assert wiki_store.document_exists("src/merged")
        merged = wiki_store.read_document("src/merged")
        assert "Content A" in merged.content
        # Sources should be deleted (redirect_sources=True)
        assert not wiki_store.document_exists("src/a")
        assert not wiki_store.document_exists("src/b")

    def test_execute_split(self, recorder, wiki_store):
        """_execute_split creates sub-documents from sections."""
        _write_doc(
            wiki_store,
            "topics/big",
            "Big Topic",
            "# Big Topic\n\nOverview text.\n\n## Sub A\n\nSub A details.\n\n## Sub B\n\nSub B details.",
            category="topics",
            tags=["big"],
        )

        plan = SplitPlan(
            plan_type=PlanType.SPLIT,
            target_path="topics/big",
            reason="Too large",
            sections_to_split=[
                {"new_path": "topics/sub_a", "content": "# Sub A\n\nSub A details."},
                {"new_path": "topics/sub_b", "content": "# Sub B\n\nSub B details."},
            ],
            summary_for_main="# Big Topic\n\nSee [[topics/sub_a]] and [[topics/sub_b]].",
        )

        result = recorder._execute_split(plan)

        assert "topics/sub_a" in result
        assert "topics/sub_b" in result
        assert wiki_store.document_exists("topics/sub_a")
        assert wiki_store.document_exists("topics/sub_b")
        # Main doc updated with summary
        main = wiki_store.read_document("topics/big")
        assert "See" in main.content or "sub_a" in main.related


# ── Full pipeline ─────────────────────────────────────────────────────


class TestRecordPipeline:
    def test_record_creates_document(self, recorder, wiki_store, agent):
        """End-to-end record() creates a new document."""
        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="conversation",
                key_topic="preferences",
                specific_content="User prefers Python",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.9,
                importance_score=0.8,
                suggested_action=PlanType.CREATE,
                target_documents=["users/preferences"],
            )
        )

        agent.plan = MagicMock(
            return_value=[
                CreatePlan(
                    plan_type=PlanType.CREATE,
                    target_path="users/preferences",
                    reason="Store user preference",
                    content="User prefers Python",
                    metadata=DocumentMetadata(
                        title="User Preferences",
                        category="users",
                        tags=["preferences", "python"],
                    ),
                )
            ]
        )

        agent.generate_document = MagicMock(
            return_value="# User Preferences\n\nUser prefers Python for development."
        )

        result = recorder.record("User prefers Python for development")

        assert result.success
        assert "Created: users/preferences" in result.actions_taken
        assert "users/preferences" in result.documents_affected
        assert wiki_store.document_exists("users/preferences")

    def test_record_modifies_document(self, recorder, wiki_store, agent):
        """End-to-end record() modifies an existing document."""
        _write_doc(
            wiki_store,
            "notes/log",
            "Activity Log",
            "# Activity Log\n\nPrevious entries.",
        )

        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="conversation",
                key_topic="activity",
                specific_content="New activity",
                existing_relations=["notes/log"],
                temporal_range="timeless",
                confidence_score=0.9,
                importance_score=0.7,
                suggested_action=PlanType.MODIFY,
                target_documents=["notes/log"],
            )
        )

        agent.plan = MagicMock(
            return_value=[
                ModifyPlan(
                    plan_type=PlanType.MODIFY,
                    target_path="notes/log",
                    reason="Append new activity",
                    modifications=[
                        {"operation": "append", "content": "New activity entry."},
                    ],
                )
            ]
        )

        result = recorder.record("New activity happened")

        assert result.success
        assert "Modified: notes/log" in result.actions_taken
        doc = wiki_store.read_document("notes/log")
        assert "New activity entry." in doc.content

    def test_record_handles_error(self, recorder, agent):
        """record() returns error RecordResult on exception."""
        agent.analyze = MagicMock(side_effect=RuntimeError("LLM unavailable"))

        result = recorder.record("Something")

        assert not result.success
        assert result.error is not None
        assert "LLM unavailable" in result.error
        assert result.actions_taken == []
        assert result.documents_affected == []

    def test_record_with_dict_content(self, recorder, wiki_store, agent):
        """record() handles dict content with type and context."""
        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="structured",
                key_topic="config",
                specific_content="Config update",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.9,
                importance_score=0.8,
                suggested_action=PlanType.CREATE,
                target_documents=["config/settings"],
            )
        )

        agent.plan = MagicMock(
            return_value=[
                CreatePlan(
                    plan_type=PlanType.CREATE,
                    target_path="config/settings",
                    reason="Store config",
                    content="Config data",
                    metadata=DocumentMetadata(
                        title="Settings",
                        category="config",
                        tags=["config"],
                    ),
                )
            ]
        )

        agent.generate_document = MagicMock(return_value="# Settings\n\nConfig data")

        result = recorder.record(
            {"content": "Config data", "type": "structured", "context": {"env": "prod"}}
        )

        assert result.success
        # Verify analyze was called with type='structured'
        assert agent.analyze.call_args[0][1] == "structured"


# ── History integration ───────────────────────────────────────────────


class TestHistoryIntegration:
    def test_record_saves_version(self, recorder, wiki_store, agent):
        """Recording a new document saves a version in history."""
        agent.analyze = MagicMock(
            return_value=AnalysisResult(
                information_type="conversation",
                key_topic="versioning",
                specific_content="Version test",
                existing_relations=[],
                temporal_range="timeless",
                confidence_score=0.9,
                importance_score=0.8,
                suggested_action=PlanType.CREATE,
                target_documents=["notes/versioned"],
            )
        )

        agent.plan = MagicMock(
            return_value=[
                CreatePlan(
                    plan_type=PlanType.CREATE,
                    target_path="notes/versioned",
                    reason="Version test",
                    content="Version content",
                    metadata=DocumentMetadata(
                        title="Versioned Note",
                        category="notes",
                        tags=["version"],
                    ),
                )
            ]
        )

        agent.generate_document = MagicMock(return_value="# Versioned Note\n\nVersion content")

        recorder.record("Version test info")

        versions = wiki_store.get_versions("notes/versioned")
        assert len(versions) >= 1
        assert versions[0].created_by_operation.value == "create"

    def test_rollback_after_modify(self, recorder, wiki_store):
        """Can rollback to a previous version after modification."""
        _write_doc(
            wiki_store,
            "notes/rollback",
            "Rollback Test",
            "# Rollback Test\n\nOriginal content.",
        )

        # Save initial version
        wiki_store.save_version("notes/rollback", "create")

        # Simulate modification by appending content
        doc = wiki_store.read_document("notes/rollback")
        doc.content += "\n\nModified content."
        wiki_store.write_document("notes/rollback", doc)
        wiki_store.save_version("notes/rollback", "modify")

        # Verify we have 2 versions
        versions = wiki_store.get_versions("notes/rollback")
        assert len(versions) == 2

        # Rollback to version 1
        rollback_result = wiki_store.rollback_to_version("notes/rollback", 1)
        assert rollback_result.success
        assert rollback_result.version_restored == 1

        # Verify content is restored
        restored = wiki_store.read_document("notes/rollback")
        assert "Original content." in restored.content

    def test_history_preserved_on_split(self, recorder, wiki_store):
        """Split creates version history for both source and new documents."""
        _write_doc(
            wiki_store,
            "topics/split_me",
            "Split Source",
            "# Split Source\n\nIntro.\n\n## Section A\n\nA content.\n\n## Section B\n\nB content.",
            category="topics",
            tags=["split"],
        )

        plan = SplitPlan(
            plan_type=PlanType.SPLIT,
            target_path="topics/split_me",
            reason="Needs splitting",
            sections_to_split=[
                {"new_path": "topics/section_a", "content": "# Section A\n\nA content."},
                {"new_path": "topics/section_b", "content": "# Section B\n\nB content."},
            ],
            summary_for_main="# Split Source\n\nSplit into sub-documents.",
        )

        recorder._execute_split(plan)

        # Source document should have split version
        source_versions = wiki_store.get_versions("topics/split_me")
        assert any(v.created_by_operation.value == "split" for v in source_versions)

        # New documents should have split versions
        a_versions = wiki_store.get_versions("topics/section_a")
        assert len(a_versions) >= 1
        assert a_versions[0].created_by_operation.value == "split"

        b_versions = wiki_store.get_versions("topics/section_b")
        assert len(b_versions) >= 1
        assert b_versions[0].created_by_operation.value == "split"
