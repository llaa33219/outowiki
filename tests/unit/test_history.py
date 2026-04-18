"""Unit tests for history tracking - models and WikiStore history methods."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from outowiki.core.exceptions import WikiStoreError
from outowiki.core.store import WikiStore
from outowiki.models.content import WikiDocument
from outowiki.models.history import (
    DocumentVersion,
    HistoryEntry,
    HistoryOperation,
    RollbackResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def wiki_root(tmp_path: Path) -> Path:
    """Provide an isolated temporary wiki root directory."""
    return tmp_path / "wiki"


@pytest.fixture
def store(wiki_root: Path) -> WikiStore:
    """Create a WikiStore pointed at the isolated wiki root."""
    return WikiStore(wiki_root)


def _make_doc(
    title: str = "Test Doc",
    content: str = "Hello world",
    path: str = "test",
    tags: list[str] | None = None,
    category: str = "",
    frontmatter: dict | None = None,
    related: list[str] | None = None,
) -> WikiDocument:
    """Helper to build a WikiDocument with sensible defaults."""
    now = datetime.now()
    return WikiDocument(
        path=path,
        title=title,
        content=content,
        frontmatter=frontmatter or {},
        backlinks=[],
        created=now,
        modified=now,
        tags=tags or [],
        category=category,
        related=related or [],
    )


def _write_doc(store: WikiStore, path: str, content: str = "Initial content") -> None:
    """Write a document to the store via the normal API."""
    doc = _make_doc(title=path.split("/")[-1], content=content, path=path, category="test")
    store.write_document(path, doc)


# ═══════════════════════════════════════════════════════════════════════════
# HistoryOperation enum
# ═══════════════════════════════════════════════════════════════════════════


class TestHistoryOperation:
    """Tests for HistoryOperation enum."""

    def test_all_six_values_exist(self):
        """All six operation types are defined."""
        assert HistoryOperation.CREATE.value == "create"
        assert HistoryOperation.MODIFY.value == "modify"
        assert HistoryOperation.DELETE.value == "delete"
        assert HistoryOperation.MERGE.value == "merge"
        assert HistoryOperation.SPLIT.value == "split"
        assert HistoryOperation.ROLLBACK.value == "rollback"

    def test_enum_member_count(self):
        """Exactly 6 enum members."""
        assert len(HistoryOperation) == 6

    def test_is_string_enum(self):
        """HistoryOperation values are plain strings."""
        assert isinstance(HistoryOperation.CREATE, str)


# ═══════════════════════════════════════════════════════════════════════════
# HistoryEntry model
# ═══════════════════════════════════════════════════════════════════════════


class TestHistoryEntry:
    """Tests for HistoryEntry Pydantic model."""

    def test_creation_with_required_fields(self):
        """HistoryEntry can be created with only required fields."""
        entry = HistoryEntry(
            document_path="notes/test",
            operation=HistoryOperation.CREATE,
        )
        assert entry.document_path == "notes/test"
        assert entry.operation == HistoryOperation.CREATE

    def test_default_timestamp(self):
        """Timestamp is auto-generated when not provided."""
        before = datetime.now()
        entry = HistoryEntry(
            document_path="x",
            operation=HistoryOperation.MODIFY,
        )
        after = datetime.now()
        assert before <= entry.timestamp <= after

    def test_default_optional_fields(self):
        """Optional fields default to None or empty collections."""
        entry = HistoryEntry(
            document_path="x",
            operation=HistoryOperation.DELETE,
        )
        assert entry.content_before is None
        assert entry.content_after is None
        assert entry.metadata == {}
        assert entry.related_paths == []

    def test_create_id_returns_valid_uuid(self):
        """create_id() returns a valid UUID string."""
        eid = HistoryEntry.create_id()
        UUID(eid)  # raises ValueError if not a valid UUID

    def test_create_id_unique(self):
        """Each call to create_id() returns a different value."""
        ids = {HistoryEntry.create_id() for _ in range(20)}
        assert len(ids) == 20

    def test_entry_id_auto_generated(self):
        """entry_id is auto-generated when not provided."""
        entry = HistoryEntry(
            document_path="x",
            operation=HistoryOperation.CREATE,
        )
        UUID(entry.entry_id)

    def test_full_creation(self):
        """HistoryEntry with all fields populated."""
        entry = HistoryEntry(
            entry_id="custom-id",
            document_path="a/b",
            operation=HistoryOperation.MERGE,
            timestamp=datetime(2024, 1, 1),
            content_before="old",
            content_after="new",
            metadata={"key": "val"},
            related_paths=["c/d"],
        )
        assert entry.entry_id == "custom-id"
        assert entry.content_before == "old"
        assert entry.content_after == "new"
        assert entry.metadata["key"] == "val"
        assert entry.related_paths == ["c/d"]


# ═══════════════════════════════════════════════════════════════════════════
# DocumentVersion model
# ═══════════════════════════════════════════════════════════════════════════


class TestDocumentVersion:
    """Tests for DocumentVersion Pydantic model."""

    def test_creation(self):
        """DocumentVersion can be created with required fields."""
        dv = DocumentVersion(
            document_path="docs/readme",
            version_number=1,
            content="Hello",
            frontmatter={"title": "Readme"},
            created_by_operation=HistoryOperation.CREATE,
        )
        assert dv.document_path == "docs/readme"
        assert dv.version_number == 1
        assert dv.content == "Hello"

    def test_version_id_auto_generated(self):
        """version_id is auto-generated."""
        dv = DocumentVersion(
            document_path="x",
            version_number=1,
            content="",
            frontmatter={},
            created_by_operation=HistoryOperation.CREATE,
        )
        UUID(dv.version_id)

    def test_create_id_returns_valid_uuid(self):
        """create_id() returns a valid UUID string."""
        vid = DocumentVersion.create_id()
        UUID(vid)

    def test_default_timestamp(self):
        """created_at defaults to now."""
        before = datetime.now()
        dv = DocumentVersion(
            document_path="x",
            version_number=1,
            content="",
            frontmatter={},
            created_by_operation=HistoryOperation.MODIFY,
        )
        after = datetime.now()
        assert before <= dv.created_at <= after


# ═══════════════════════════════════════════════════════════════════════════
# RollbackResult model
# ═══════════════════════════════════════════════════════════════════════════


class TestRollbackResult:
    """Tests for RollbackResult Pydantic model."""

    def test_success_result(self):
        """Successful rollback result."""
        result = RollbackResult(
            success=True,
            document_path="notes/test",
            version_restored=3,
        )
        assert result.success is True
        assert result.version_restored == 3
        assert result.error is None

    def test_failure_result(self):
        """Failed rollback result with error message."""
        result = RollbackResult(
            success=False,
            document_path="notes/test",
            version_restored=0,
            error="Version not found",
        )
        assert result.success is False
        assert result.error == "Version not found"


# ═══════════════════════════════════════════════════════════════════════════
# WikiStore.save_version
# ═══════════════════════════════════════════════════════════════════════════


class TestSaveVersion:
    """Tests for WikiStore.save_version."""

    def test_creates_version_file(self, store: WikiStore, wiki_root: Path):
        """save_version creates a version JSON file on disk."""
        _write_doc(store, "notes/test", "Version one")
        store.save_version("notes/test", "create")

        version_dir = wiki_root / ".history" / "versions" / "notes_test"
        assert version_dir.exists()
        files = list(version_dir.glob("v*.json"))
        assert len(files) == 1

    def test_increments_version_number(self, store: WikiStore):
        """Successive saves increment the version number."""
        _write_doc(store, "inc/doc", "Content A")
        v1 = store.save_version("inc/doc", "create")
        assert v1.version_number == 1

        _write_doc(store, "inc/doc", "Content B")
        v2 = store.save_version("inc/doc", "modify")
        assert v2.version_number == 2

        _write_doc(store, "inc/doc", "Content C")
        v3 = store.save_version("inc/doc", "modify")
        assert v3.version_number == 3

    def test_version_preserves_content(self, store: WikiStore):
        """Version snapshot captures current document content."""
        _write_doc(store, "snap/test", "Snapshot content here")
        version = store.save_version("snap/test", "create")

        assert version.content == "Snapshot content here"

    def test_version_records_operation(self, store: WikiStore):
        """Version records the triggering operation type."""
        _write_doc(store, "op/test", "data")
        version = store.save_version("op/test", "modify")

        assert version.created_by_operation == HistoryOperation.MODIFY


# ═══════════════════════════════════════════════════════════════════════════
# WikiStore.get_versions
# ═══════════════════════════════════════════════════════════════════════════


class TestGetVersions:
    """Tests for WikiStore.get_versions."""

    def test_returns_sorted_versions(self, store: WikiStore):
        """Versions are returned sorted by version number."""
        _write_doc(store, "sort/doc", "V1")
        store.save_version("sort/doc", "create")

        _write_doc(store, "sort/doc", "V2")
        store.save_version("sort/doc", "modify")

        _write_doc(store, "sort/doc", "V3")
        store.save_version("sort/doc", "modify")

        versions = store.get_versions("sort/doc")
        assert [v.version_number for v in versions] == [1, 2, 3]

    def test_empty_for_new_document(self, store: WikiStore):
        """No versions returned for a document with no history."""
        assert store.get_versions("nonexistent/doc") == []


# ═══════════════════════════════════════════════════════════════════════════
# WikiStore.get_version_content
# ═══════════════════════════════════════════════════════════════════════════


class TestGetVersionContent:
    """Tests for WikiStore.get_version_content."""

    def test_returns_correct_content(self, store: WikiStore):
        """Returns the content stored in the requested version."""
        _write_doc(store, "vc/doc", "Alpha")
        store.save_version("vc/doc", "create")

        _write_doc(store, "vc/doc", "Beta")
        store.save_version("vc/doc", "modify")

        assert store.get_version_content("vc/doc", 1) == "Alpha"
        assert store.get_version_content("vc/doc", 2) == "Beta"

    def test_raises_for_invalid_version(self, store: WikiStore):
        """Raises WikiStoreError when version does not exist."""
        _write_doc(store, "vc/missing", "X")
        store.save_version("vc/missing", "create")

        with pytest.raises(WikiStoreError, match="Version 99 not found"):
            store.get_version_content("vc/missing", 99)


# ═══════════════════════════════════════════════════════════════════════════
# WikiStore.rollback_to_version
# ═══════════════════════════════════════════════════════════════════════════


class TestRollbackToVersion:
    """Tests for WikiStore.rollback_to_version."""

    def test_restores_content(self, store: WikiStore):
        """Rollback restores the content from the target version."""
        _write_doc(store, "rb/doc", "Original")
        store.save_version("rb/doc", "create")

        _write_doc(store, "rb/doc", "Modified")
        store.save_version("rb/doc", "modify")

        store.rollback_to_version("rb/doc", 1)

        doc = store.read_document("rb/doc")
        assert "Original" in doc.content

    def test_returns_success_result(self, store: WikiStore):
        """Successful rollback returns a success RollbackResult."""
        _write_doc(store, "rb/ok", "V1")
        store.save_version("rb/ok", "create")

        _write_doc(store, "rb/ok", "V2")
        store.save_version("rb/ok", "modify")

        result = store.rollback_to_version("rb/ok", 1)

        assert result.success is True
        assert result.version_restored == 1
        assert result.error is None

    def test_returns_failure_for_invalid_version(self, store: WikiStore):
        """Returns failure RollbackResult for non-existent version."""
        _write_doc(store, "rb/fail", "Only version")
        store.save_version("rb/fail", "create")

        result = store.rollback_to_version("rb/fail", 999)

        assert result.success is False
        assert result.version_restored == 0
        assert result.error is not None


# ═══════════════════════════════════════════════════════════════════════════
# WikiStore.get_history
# ═══════════════════════════════════════════════════════════════════════════


class TestGetHistory:
    """Tests for WikiStore.get_history."""

    def test_filters_by_document_path(self, store: WikiStore):
        """Only entries matching the given path are returned."""
        _write_doc(store, "hist/a", "A")
        store.save_version("hist/a", "create")

        _write_doc(store, "hist/b", "B")
        store.save_version("hist/b", "create")

        entries = store.get_history("hist/a")
        assert all(e.document_path == "hist/a" for e in entries)
        assert len(entries) >= 1

    def test_empty_for_unknown_path(self, store: WikiStore):
        """No entries for a path with no history."""
        assert store.get_history("no/such/path") == []


# ═══════════════════════════════════════════════════════════════════════════
# WikiStore.get_recent_changes
# ═══════════════════════════════════════════════════════════════════════════


class TestGetRecentChanges:
    """Tests for WikiStore.get_recent_changes."""

    def test_returns_latest_n_entries(self, store: WikiStore):
        """Returns at most *limit* entries, newest first."""
        for i in range(5):
            _write_doc(store, f"recent/doc{i}", f"Content {i}")
            store.save_version(f"recent/doc{i}", "create")

        recent = store.get_recent_changes(limit=3)
        assert len(recent) == 3

    def test_returns_all_when_fewer_than_limit(self, store: WikiStore):
        """If fewer entries than limit, all are returned."""
        _write_doc(store, "recent/only", "X")
        store.save_version("recent/only", "create")

        recent = store.get_recent_changes(limit=100)
        assert len(recent) >= 1
