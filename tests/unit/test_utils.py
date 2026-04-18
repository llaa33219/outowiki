"""Tests for utility functions in outowiki.utils."""

import json
from pathlib import Path

import pytest

from outowiki.utils.backlinks import BacklinkManager
from outowiki.utils.filesystem import (
    delete_file,
    ensure_directory,
    list_files,
    list_folders,
    read_file,
    relative_to,
    safe_path,
    write_file,
)
from outowiki.utils.markdown import (
    create_frontmatter,
    estimate_tokens,
    extract_links,
    extract_sections,
    parse_frontmatter,
    replace_links,
)


# ---------------------------------------------------------------------------
# filesystem.py
# ---------------------------------------------------------------------------


class TestSafePath:
    def test_valid_path(self, tmp_path: Path):
        base = tmp_path / "wiki"
        base.mkdir()
        result = safe_path(base, "notes/test.md")
        assert result == base.resolve() / "notes" / "test.md"

    def test_traversal_detected(self, tmp_path: Path):
        base = tmp_path / "wiki"
        base.mkdir()
        with pytest.raises(ValueError, match="Path traversal detected"):
            safe_path(base, "../../../etc/passwd")

    def test_absolute_path_stripped(self, tmp_path: Path):
        base = tmp_path / "wiki"
        base.mkdir()
        result = safe_path(base, "/absolute/path/doc.md")
        assert result == base.resolve() / "absolute" / "path" / "doc.md"


class TestEnsureDirectory:
    def test_creates_directory(self, tmp_path: Path):
        target = tmp_path / "new_dir" / "sub"
        ensure_directory(target)
        assert target.is_dir()

    def test_no_error_if_exists(self, tmp_path: Path):
        target = tmp_path / "existing"
        target.mkdir()
        ensure_directory(target)  # should not raise
        assert target.is_dir()


class TestReadFile:
    def test_reads_utf8(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("héllo wörld", encoding="utf-8")
        assert read_file(f) == "héllo wörld"

    def test_handles_encoding_errors(self, tmp_path: Path):
        f = tmp_path / "bad.bin"
        f.write_bytes(b"\xff\xfe invalid utf8 \x80")
        result = read_file(f)
        assert isinstance(result, str)
        # Should not raise; bytes are replaced


class TestWriteFile:
    def test_atomic_write(self, tmp_path: Path):
        f = tmp_path / "doc.md"
        write_file(f, "content", atomic=True)
        assert f.read_text(encoding="utf-8") == "content"

    def test_non_atomic_write(self, tmp_path: Path):
        f = tmp_path / "doc.md"
        write_file(f, "content", atomic=False)
        assert f.read_text(encoding="utf-8") == "content"

    def test_creates_parent_dirs(self, tmp_path: Path):
        f = tmp_path / "deep" / "nested" / "doc.md"
        write_file(f, "deep content")
        assert f.read_text(encoding="utf-8") == "deep content"


class TestDeleteFile:
    def test_deletes_file(self, tmp_path: Path):
        f = tmp_path / "gone.md"
        f.write_text("bye")
        delete_file(f)
        assert not f.exists()

    def test_raises_for_directory(self, tmp_path: Path):
        d = tmp_path / "adir"
        d.mkdir()
        with pytest.raises(IsADirectoryError):
            delete_file(d)


class TestListFiles:
    def test_lists_md_files(self, tmp_path: Path):
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.txt").write_text("c")
        result = list_files(tmp_path)
        names = [p.name for p in result]
        assert names == ["a.md", "b.md"]

    def test_empty_folder(self, tmp_path: Path):
        result = list_files(tmp_path)
        assert result == []


class TestListFolders:
    def test_lists_subdirs(self, tmp_path: Path):
        (tmp_path / "dir_a").mkdir()
        (tmp_path / "dir_b").mkdir()
        (tmp_path / "file.md").write_text("x")
        result = list_folders(tmp_path)
        names = [p.name for p in result]
        assert names == ["dir_a", "dir_b"]

    def test_no_subdirs(self, tmp_path: Path):
        (tmp_path / "file.md").write_text("x")
        result = list_folders(tmp_path)
        assert result == []


class TestRelativeTo:
    def test_correct_relative_path(self, tmp_path: Path):
        base = tmp_path / "wiki"
        base.mkdir()
        target = base / "notes" / "doc.md"
        result = relative_to(base, target)
        assert result == "notes/doc.md"

    def test_forward_slashes(self, tmp_path: Path):
        base = tmp_path / "wiki"
        base.mkdir()
        target = base / "a" / "b" / "c.md"
        result = relative_to(base, target)
        assert "/" in result
        assert "\\" not in result


# ---------------------------------------------------------------------------
# markdown.py
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = "---\ntitle: Test\ntags:\n  - a\n---\nBody text here.\n"
        meta, body = parse_frontmatter(content)
        assert meta["title"] == "Test"
        assert meta["tags"] == ["a"]
        assert body == "Body text here."

    def test_no_frontmatter(self):
        content = "Just some text without frontmatter."
        meta, body = parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_invalid_yaml(self):
        content = "---\n: invalid: yaml: [\n---\nBody\n"
        meta, body = parse_frontmatter(content)
        # Should fall back to empty dict and return raw content
        assert meta == {}
        assert body == content.strip()

    def test_empty_content(self):
        meta, body = parse_frontmatter("")
        assert meta == {}
        assert body == ""


class TestCreateFrontmatter:
    def test_basic_frontmatter(self):
        result = create_frontmatter({"title": "My Page"})
        assert result.startswith("---\n")
        assert result.strip().endswith("---")
        assert "title: My Page" in result

    def test_default_timestamps(self):
        result = create_frontmatter({"title": "X"})
        assert "created:" in result
        assert "modified:" in result

    def test_custom_fields(self):
        result = create_frontmatter({"title": "X", "author": "Alice"})
        assert "author: Alice" in result


class TestExtractLinks:
    def test_basic_link(self):
        assert extract_links("See [[target]] for info.") == ["target"]

    def test_link_with_display(self):
        assert extract_links("Click [[target|display text]]") == ["target"]

    def test_deduplication(self):
        assert extract_links("[[a]] and [[a]] and [[b]]") == ["a", "b"]

    def test_no_links(self):
        assert extract_links("No links here.") == []


class TestReplaceLinks:
    def test_basic_replace(self):
        result = replace_links("See [[old]] here.", {"old": "new"})
        assert result == "See [[new]] here."

    def test_preserve_display(self):
        result = replace_links("[[old|display]]", {"old": "new"})
        assert result == "[[new||display]]"

    def test_no_match(self):
        original = "See [[keep]] here."
        result = replace_links(original, {"other": "new"})
        assert result == original


class TestExtractSections:
    def test_single_section(self):
        content = "# Title\n\nParagraph here.\n"
        sections = extract_sections(content)
        assert len(sections) == 1
        assert sections[0]["level"] == "1"
        assert sections[0]["title"] == "Title"
        assert "Paragraph here." in sections[0]["content"]

    def test_multiple_sections(self):
        content = "# One\n\nA\n\n## Two\n\nB\n"
        sections = extract_sections(content)
        assert len(sections) == 2
        assert sections[0]["title"] == "One"
        assert sections[1]["title"] == "Two"

    def test_nested_headers(self):
        content = "# H1\n\nTop\n\n## H2\n\nMid\n\n### H3\n\nDeep\n"
        sections = extract_sections(content)
        assert len(sections) == 3
        assert sections[0]["level"] == "1"
        assert sections[1]["level"] == "2"
        assert sections[2]["level"] == "3"

    def test_no_headers(self):
        content = "Just text.\nNo headers.\n"
        sections = extract_sections(content)
        assert sections == []


class TestEstimateTokens:
    def test_short_content(self):
        assert estimate_tokens("abc") == 0  # 3 chars // 4 = 0

    def test_long_content(self):
        text = "a" * 100
        assert estimate_tokens(text) == 25

    def test_empty_content(self):
        assert estimate_tokens("") == 0


# ---------------------------------------------------------------------------
# backlinks.py
# ---------------------------------------------------------------------------


class TestBacklinkManager:
    def _make_doc(self, wiki: Path, name: str, content: str) -> Path:
        """Helper: create a markdown doc in the wiki root."""
        p = wiki / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_load_existing_index(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        index_data = {"target": ["source_a", "source_b"]}
        (wiki / ".backlinks.json").write_text(json.dumps(index_data))
        mgr = BacklinkManager(wiki)
        doc = wiki / "target.md"
        result = mgr.get_backlinks(doc)
        assert result == ["source_a", "source_b"]

    def test_load_corrupt_index(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        (wiki / ".backlinks.json").write_text("NOT VALID JSON{{{")
        mgr = BacklinkManager(wiki)
        # Should not raise; index starts empty
        doc = wiki / "anything.md"
        assert mgr.get_backlinks(doc) == []

    def test_update_backlinks(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        mgr = BacklinkManager(wiki)
        doc = self._make_doc(wiki, "alpha.md", "# Alpha\nSee [[beta]] and [[gamma]].\n")
        links = mgr.scan_document(doc)
        mgr.update_backlinks(doc, links)

        beta = wiki / "beta.md"
        result = mgr.get_backlinks(beta)
        assert "alpha" in result

    def test_get_backlinks_empty(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        mgr = BacklinkManager(wiki)
        doc = wiki / "lonely.md"
        assert mgr.get_backlinks(doc) == []

    def test_remove_document(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        mgr = BacklinkManager(wiki)
        doc = self._make_doc(wiki, "src.md", "[[dest]]\n")
        mgr.update_backlinks(doc, mgr.scan_document(doc))

        dest = wiki / "dest.md"
        assert "src" in mgr.get_backlinks(dest)

        mgr.remove_document(doc)
        assert mgr.get_backlinks(dest) == []

    def test_rebuild_index(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        self._make_doc(wiki, "page_a.md", "# A\nLinks: [[page_b]]\n")
        self._make_doc(wiki, "page_b.md", "# B\nLinks: [[page_a]]\n")

        mgr = BacklinkManager(wiki)
        mgr.rebuild_index()

        page_b = wiki / "page_b.md"
        backlinks_b = mgr.get_backlinks(page_b)
        assert "page_a" in backlinks_b

        page_a = wiki / "page_a.md"
        backlinks_a = mgr.get_backlinks(page_a)
        assert "page_b" in backlinks_a

    def test_update_replaces_old_links(self, tmp_path: Path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        mgr = BacklinkManager(wiki)
        doc = self._make_doc(wiki, "src.md", "[[old_target]]\n")
        mgr.update_backlinks(doc, mgr.scan_document(doc))

        old = wiki / "old_target.md"
        assert "src" in mgr.get_backlinks(old)

        # Now update with new links — old_target should lose src
        mgr.update_backlinks(doc, ["new_target"])

        assert mgr.get_backlinks(old) == []
        new = wiki / "new_target.md"
        assert "src" in mgr.get_backlinks(new)
