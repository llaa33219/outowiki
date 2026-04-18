"""Backlink tracking and management for OutoWiki documents."""

from __future__ import annotations

import json
from pathlib import Path

from .filesystem import list_files, read_file, relative_to, write_file
from .markdown import extract_links


class BacklinkManager:
    """Manages the backlink index mapping targets to source documents.

    The index is persisted as .backlinks.json in the wiki root.
    Structure: {target_path: [source_path, ...], ...}
    """

    INDEX_FILE = ".backlinks.json"

    def __init__(self, wiki_root: Path) -> None:
        self.wiki_root = wiki_root
        self._index: dict[str, set[str]] = {}
        self._load_index()

    def _index_path(self) -> Path:
        return self.wiki_root / self.INDEX_FILE

    def _load_index(self) -> None:
        path = self._index_path()
        if path.is_file():
            try:
                data = json.loads(read_file(path))
                self._index = {k: set(v) for k, v in data.items()}
            except (json.JSONDecodeError, ValueError):
                self._index = {}
        else:
            self._index = {}

    def _save_index(self) -> None:
        data = {k: sorted(v) for k, v in self._index.items() if v}
        write_file(self._index_path(), json.dumps(data, indent=2, ensure_ascii=False))

    def _normalize(self, path_ref: str) -> str:
        if path_ref.endswith(".md"):
            return path_ref[:-3]
        return path_ref

    def _to_relative(self, doc_path: Path) -> str:
        return relative_to(self.wiki_root, doc_path)

    def scan_document(self, doc_path: Path) -> list[str]:
        """Extract wiki links from a document and return target paths."""
        content = read_file(doc_path)
        return extract_links(content)

    def update_backlinks(self, doc_path: Path, links: list[str]) -> None:
        """Update the backlink index for a source document and its link targets."""
        source = self._normalize(self._to_relative(doc_path))

        old_links: set[str] = set()
        for target, sources in self._index.items():
            if source in sources:
                old_links.add(target)

        new_links = set(self._normalize(l) for l in links)

        for target in old_links - new_links:
            self._index[target].discard(source)
            if not self._index[target]:
                del self._index[target]

        for target in new_links:
            if target not in self._index:
                self._index[target] = set()
            self._index[target].add(source)

        self._save_index()

    def get_backlinks(self, doc_path: Path) -> list[str]:
        """Return sorted list of source documents that link to doc_path."""
        target = self._normalize(self._to_relative(doc_path))
        sources = self._index.get(target, set())
        return sorted(sources)

    def remove_document(self, doc_path: Path) -> None:
        """Remove a document from the backlink index entirely."""
        source = self._normalize(self._to_relative(doc_path))

        for target in list(self._index.keys()):
            self._index[target].discard(source)
            if not self._index[target]:
                del self._index[target]

        self._index.pop(source, None)
        self._save_index()

    def rebuild_index(self) -> None:
        """Scan all markdown documents and rebuild the entire index."""
        self._index = {}
        md_files = list_files(self.wiki_root, "*.md")
        for md_file in md_files:
            try:
                links = self.scan_document(md_file)
                source = self._normalize(self._to_relative(md_file))
                for target in links:
                    target = self._normalize(target)
                    if target not in self._index:
                        self._index[target] = set()
                    self._index[target].add(source)
            except OSError:
                continue
        self._save_index()
