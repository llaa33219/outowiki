"""Unit tests for WikiStore - wiki storage interface."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from outowiki.core.exceptions import WikiStoreError
from outowiki.core.store import WikiStore
from outowiki.models.content import WikiDocument


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


# ===========================================================================
# __init__
# ===========================================================================


class TestInit:
    def test_creates_root_directory(self, wiki_root: Path) -> None:
        """WikiStore.__init__ should create the root directory if missing."""
        assert not wiki_root.exists()
        WikiStore(wiki_root)
        assert wiki_root.is_dir()

    def test_root_is_resolved(self, wiki_root: Path) -> None:
        """Root path should be stored as an absolute resolved Path."""
        store = WikiStore(wiki_root)
        assert store.root == wiki_root.resolve()

    def test_initializes_backlinks(self, store: WikiStore) -> None:
        """BacklinkManager should be initialised on the store."""
        from outowiki.utils.backlinks import BacklinkManager

        assert isinstance(store.backlinks, BacklinkManager)

    def test_existing_root_not_broken(self, wiki_root: Path) -> None:
        """Init should work even when root already exists."""
        wiki_root.mkdir(parents=True)
        store = WikiStore(wiki_root)
        assert store.root.is_dir()


# ===========================================================================
# _doc_path
# ===========================================================================


class TestDocPath:
    def test_adds_md_extension(self, store: WikiStore) -> None:
        p = store._doc_path("notes")
        assert p.name == "notes.md"

    def test_preserves_existing_md_extension(self, store: WikiStore) -> None:
        p = store._doc_path("notes.md")
        assert p.name == "notes.md"

    def test_subfolder_path(self, store: WikiStore) -> None:
        p = store._doc_path("folder/notes")
        assert p.name == "notes.md"
        assert "folder" in p.parts

    def test_path_traversal_raises(self, store: WikiStore) -> None:
        """Attempting to escape the wiki root via '..' should raise."""
        with pytest.raises(ValueError, match="Path traversal"):
            store._doc_path("../../etc/passwd")


# ===========================================================================
# read_document
# ===========================================================================


class TestReadDocument:
    def test_nonexistent_raises(self, store: WikiStore) -> None:
        with pytest.raises(WikiStoreError, match="Document not found"):
            store.read_document("no_such_doc")

    def test_reads_existing_document(self, store: WikiStore) -> None:
        store.write_document("hello", _make_doc(title="Hello", content="body text"))
        doc = store.read_document("hello")
        assert isinstance(doc, WikiDocument)
        assert doc.title == "Hello"
        assert "body text" in doc.content

    def test_parses_frontmatter(self, store: WikiStore) -> None:
        doc = _make_doc(
            title="FM Test",
            content="some content",
            tags=["a", "b"],
            category="testing",
        )
        store.write_document("fm", doc)
        result = store.read_document("fm")
        assert "a" in result.tags
        assert result.category == "testing"

    def test_extracts_backlinks(self, store: WikiStore) -> None:
        """Document A links to B → reading B should list A as a backlink."""
        doc_a = _make_doc(title="A", content="See also [[target_b]]")
        store.write_document("doc_a", doc_a)

        doc_b = _make_doc(title="B", content="Target doc")
        store.write_document("target_b", doc_b)

        result = store.read_document("target_b")
        # doc_a links to target_b, so target_b's backlinks should include doc_a
        assert len(result.backlinks) >= 1

    def test_path_with_and_without_extension(self, store: WikiStore) -> None:
        """read_document('foo') and read_document('foo.md') resolve the same file."""
        store.write_document("ext_test", _make_doc(content="data"))
        d1 = store.read_document("ext_test")
        d2 = store.read_document("ext_test.md")
        assert d1.content == d2.content


# ===========================================================================
# write_document
# ===========================================================================


class TestWriteDocument:
    def test_creates_file(self, store: WikiStore) -> None:
        store.write_document("new_doc", _make_doc(content="written"))
        assert (store.root / "new_doc.md").is_file()

    def test_creates_parent_directories(self, store: WikiStore) -> None:
        store.write_document("deep/nested/doc", _make_doc(content="deep"))
        assert (store.root / "deep" / "nested" / "doc.md").is_file()

    def test_sets_modified_timestamp(self, store: WikiStore) -> None:
        doc = _make_doc(content="timestamp test")
        store.write_document("ts", doc)
        result = store.read_document("ts")
        assert isinstance(result.modified, datetime)

    def test_sets_created_if_missing(self, store: WikiStore) -> None:
        doc = _make_doc(content="create test")
        store.write_document("created_test", doc)
        result = store.read_document("created_test")
        assert isinstance(result.created, datetime)

    def test_preserves_existing_created(self, store: WikiStore) -> None:
        original_created = datetime(2024, 1, 1, 12, 0, 0)
        doc = _make_doc(content="preserve created")
        doc.created = original_created
        store.write_document("preserve_ts", doc)
        result = store.read_document("preserve_ts")
        # The created timestamp should be preserved (within ISO format round-trip)
        assert result.created.year == 2024
        assert result.created.month == 1
        assert result.created.day == 1

    def test_updates_backlinks(self, store: WikiStore) -> None:
        """Writing a document with wiki links should update the backlink index."""
        doc = _make_doc(content="Check [[other_page]] for details.")
        store.write_document("linker", doc)
        blinks = store.backlinks.get_backlinks(store.root / "other_page.md")
        assert len(blinks) >= 1

    def test_overwrites_existing(self, store: WikiStore) -> None:
        store.write_document("overwrite", _make_doc(content="v1"))
        store.write_document("overwrite", _make_doc(content="v2"))
        doc = store.read_document("overwrite")
        assert "v2" in doc.content


# ===========================================================================
# delete_document
# ===========================================================================


class TestDeleteDocument:
    def test_deletes_existing(self, store: WikiStore) -> None:
        store.write_document("del_me", _make_doc(content="bye"))
        assert store.document_exists("del_me")
        store.delete_document("del_me")
        assert not store.document_exists("del_me")

    def test_nonexistent_raises(self, store: WikiStore) -> None:
        with pytest.raises(WikiStoreError, match="Document not found"):
            store.delete_document("ghost")

    def test_removes_backlinks_by_default(self, store: WikiStore) -> None:
        doc = _make_doc(content="Link to [[target]]")
        store.write_document("source", doc)
        store.delete_document("source")
        # Backlink index should no longer contain 'source'
        blinks = store.backlinks.get_backlinks(store.root / "target.md")
        assert "source" not in blinks

    def test_skip_backlinks_flag(self, store: WikiStore) -> None:
        store.write_document("skip_bl", _make_doc(content="[[x]]"))
        # Should not raise even with remove_backlinks=False
        store.delete_document("skip_bl", remove_backlinks=False)
        assert not store.document_exists("skip_bl")


# ===========================================================================
# document_exists
# ===========================================================================


class TestDocumentExists:
    def test_returns_true_for_existing(self, store: WikiStore) -> None:
        store.write_document("exists_check", _make_doc(content="yes"))
        assert store.document_exists("exists_check") is True

    def test_returns_false_for_missing(self, store: WikiStore) -> None:
        assert store.document_exists("missing") is False

    def test_works_with_extension(self, store: WikiStore) -> None:
        store.write_document("ext_chk", _make_doc(content="data"))
        assert store.document_exists("ext_chk.md") is True


# ===========================================================================
# list_folder
# ===========================================================================


class TestListFolder:
    def test_lists_root(self, store: WikiStore) -> None:
        store.write_document("root_doc", _make_doc(content="root"))
        result = store.list_folder()
        assert "root_doc" in result["files"]
        assert isinstance(result["folders"], list)

    def test_lists_subfolder(self, store: WikiStore) -> None:
        store.write_document("sub/item", _make_doc(content="sub item"))
        result = store.list_folder("sub")
        assert "item" in result["files"]

    def test_shows_folders(self, store: WikiStore) -> None:
        store.create_folder("my_folder")
        result = store.list_folder()
        assert "my_folder" in result["folders"]

    def test_nonexistent_raises(self, store: WikiStore) -> None:
        with pytest.raises(WikiStoreError, match="Folder not found"):
            store.list_folder("no_such_folder")

    def test_empty_folder(self, store: WikiStore) -> None:
        store.create_folder("empty_dir")
        result = store.list_folder("empty_dir")
        assert result["files"] == []
        assert result["folders"] == []


# ===========================================================================
# create_folder
# ===========================================================================


class TestCreateFolder:
    def test_creates_new_folder(self, store: WikiStore) -> None:
        store.create_folder("new_folder")
        assert (store.root / "new_folder").is_dir()

    def test_creates_nested_folders(self, store: WikiStore) -> None:
        store.create_folder("a/b/c")
        assert (store.root / "a" / "b" / "c").is_dir()

    def test_idempotent_on_existing(self, store: WikiStore) -> None:
        store.create_folder("dup")
        store.create_folder("dup")  # should not raise
        assert (store.root / "dup").is_dir()


# ===========================================================================
# delete_folder
# ===========================================================================


class TestDeleteFolder:
    def test_deletes_empty_folder(self, store: WikiStore) -> None:
        store.create_folder("removable")
        store.delete_folder("removable")
        assert not (store.root / "removable").exists()

    def test_recursive_deletes_contents(self, store: WikiStore) -> None:
        store.create_folder("full/nested")
        store.write_document("full/doc", _make_doc(content="inside"))
        store.delete_folder("full", recursive=True)
        assert not (store.root / "full").exists()

    def test_nonexistent_raises(self, store: WikiStore) -> None:
        with pytest.raises(WikiStoreError, match="Folder not found"):
            store.delete_folder("ghost_folder")

    def test_non_recursive_nonempty_raises(self, store: WikiStore) -> None:
        store.create_folder("notempty")
        store.write_document("notempty/file", _make_doc(content="data"))
        with pytest.raises(WikiStoreError):
            store.delete_folder("notempty", recursive=False)


# ===========================================================================
# get_index
# ===========================================================================


class TestGetIndex:
    def test_returns_summaries(self, store: WikiStore) -> None:
        store.write_document("indexed", _make_doc(title="Indexed", content="Summary line here."))
        idx = store.get_index()
        assert "indexed" in idx
        assert idx["indexed"]["title"] == "Indexed"
        assert "Summary line here" in idx["indexed"]["summary"]

    def test_empty_folder_returns_empty(self, store: WikiStore) -> None:
        store.create_folder("empty_idx")
        idx = store.get_index("empty_idx")
        assert idx == {}

    def test_skips_invalid_files(self, store: WikiStore) -> None:
        """A corrupted .md file should be silently skipped."""
        bad_file = store.root / "broken.md"
        bad_file.write_text("---\ninvalid: [yaml: broken\n---\ncontent")
        idx = store.get_index()
        # Should not crash; broken file may or may not appear
        assert isinstance(idx, dict)

    def test_includes_modified_timestamp(self, store: WikiStore) -> None:
        store.write_document("ts_idx", _make_doc(title="TS", content="content"))
        idx = store.get_index()
        assert "modified" in idx["ts_idx"]
        assert idx["ts_idx"]["modified"] != ""

    def test_title_defaults_to_stem(self, store: WikiStore) -> None:
        """If no title in frontmatter, the file stem should be used."""
        # Write a file manually without a title in frontmatter
        raw = "---\ntags: []\n---\n\nJust some text."
        f = store.root / "stemtest.md"
        f.write_text(raw)
        idx = store.get_index()
        assert idx["stemtest"]["title"] == "stemtest"
