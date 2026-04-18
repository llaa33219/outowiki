"""Wiki storage interface for file system operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import json
import uuid

from ..models.content import WikiDocument, DocumentMetadata
from ..models.history import HistoryEntry, DocumentVersion, RollbackResult, HistoryOperation
from ..utils.markdown import parse_frontmatter, create_frontmatter
from ..utils.filesystem import (
    safe_path, ensure_directory, read_file, write_file,
    delete_file, list_files, list_folders, relative_to
)
from ..utils.backlinks import BacklinkManager
from .exceptions import WikiStoreError


class WikiStore:
    """File system interface for wiki storage.

    Manages markdown documents in a folder-based hierarchy.
    Handles CRUD operations, folder management, and backlink tracking.

    Example:
        store = WikiStore("./my_wiki")
        doc = store.read_document("users/alice/profile.md")
        store.write_document("users/alice/notes.md", new_doc)
    """

    def __init__(self, root_path: str | Path):
        """Initialize wiki store.

        Args:
            root_path: Root directory for wiki storage
        """
        self.root = Path(root_path).resolve()
        ensure_directory(self.root)
        self.backlinks = BacklinkManager(self.root)

    def _doc_path(self, path: str) -> Path:
        """Convert relative path to absolute, ensuring .md extension."""
        if not path.endswith('.md'):
            path = path + '.md'
        return safe_path(self.root, path)

    def read_document(self, path: str) -> WikiDocument:
        """Read a wiki document.

        Args:
            path: Relative path from wiki root (with or without .md)

        Returns:
            WikiDocument instance

        Raises:
            WikiStoreError: If document doesn't exist or is invalid
        """
        doc_path = self._doc_path(path)
        if not doc_path.exists():
            raise WikiStoreError(f"Document not found: {path}")

        try:
            content = read_file(doc_path)
            frontmatter, body = parse_frontmatter(content)

            rel_path = relative_to(self.root, doc_path)
            backlinks = self.backlinks.get_backlinks(doc_path)

            return WikiDocument(
                path=rel_path,
                title=frontmatter.get('title', doc_path.stem),
                content=body,
                frontmatter=frontmatter,
                backlinks=backlinks,
                created=datetime.fromisoformat(frontmatter.get('created', datetime.now().isoformat())),
                modified=datetime.fromisoformat(frontmatter.get('modified', datetime.now().isoformat())),
                tags=frontmatter.get('tags', []),
                category=frontmatter.get('category', ''),
                related=frontmatter.get('related', [])
            )
        except WikiStoreError:
            raise
        except Exception as e:
            raise WikiStoreError(f"Failed to read document: {e}") from e

    def write_document(self, path: str, document: WikiDocument) -> None:
        """Write a wiki document.

        Args:
            path: Relative path from wiki root
            document: WikiDocument to write

        Raises:
            WikiStoreError: If write fails
        """
        doc_path = self._doc_path(path)
        ensure_directory(doc_path.parent)

        try:
            # Update timestamps
            now = datetime.now()
            document.modified = now
            if not document.created:
                document.created = now

            # Build frontmatter
            metadata = {
                'title': document.title,
                'created': document.created.isoformat(),
                'modified': document.modified.isoformat(),
                'tags': document.tags,
                'category': document.category,
                'related': document.related,
                **document.frontmatter
            }

            # Build full content
            full_content = create_frontmatter(metadata) + '\n\n' + document.content

            # Write file
            write_file(doc_path, full_content)

            # Update backlinks
            from ..utils.markdown import extract_links
            links = extract_links(document.content)
            self.backlinks.update_backlinks(doc_path, links)

        except Exception as e:
            raise WikiStoreError(f"Failed to write document: {e}") from e

    def delete_document(self, path: str, remove_backlinks: bool = True) -> None:
        """Delete a wiki document.

        Args:
            path: Relative path from wiki root
            remove_backlinks: Whether to update backlinks in other documents

        Raises:
            WikiStoreError: If deletion fails
        """
        doc_path = self._doc_path(path)
        if not doc_path.exists():
            raise WikiStoreError(f"Document not found: {path}")

        try:
            if remove_backlinks:
                self.backlinks.remove_document(doc_path)
            delete_file(doc_path)
        except WikiStoreError:
            raise
        except Exception as e:
            raise WikiStoreError(f"Failed to delete document: {e}") from e

    def document_exists(self, path: str) -> bool:
        """Check if a document exists.

        Args:
            path: Relative path from wiki root

        Returns:
            True if document exists
        """
        doc_path = self._doc_path(path)
        return doc_path.exists()

    def list_folder(self, folder_path: str = "") -> Dict[str, List[str]]:
        """List contents of a folder.

        Args:
            folder_path: Relative path from wiki root (empty for root)

        Returns:
            Dict with 'folders' and 'files' keys

        Raises:
            WikiStoreError: If folder doesn't exist
        """
        folder = safe_path(self.root, folder_path) if folder_path else self.root
        if not folder.exists():
            raise WikiStoreError(f"Folder not found: {folder_path}")

        folders = [f.name for f in list_folders(folder)]
        files = [f.stem for f in list_files(folder, "*.md")]

        return {'folders': folders, 'files': files}

    def create_folder(self, folder_path: str) -> None:
        """Create a folder (and parents if needed).

        Args:
            folder_path: Relative path from wiki root

        Raises:
            WikiStoreError: If creation fails
        """
        folder = safe_path(self.root, folder_path)
        try:
            ensure_directory(folder)
        except Exception as e:
            raise WikiStoreError(f"Failed to create folder: {e}") from e

    def delete_folder(self, folder_path: str, recursive: bool = False) -> None:
        """Delete a folder.

        Args:
            folder_path: Relative path from wiki root
            recursive: If True, delete folder and contents; if False, only empty folders

        Raises:
            WikiStoreError: If deletion fails
        """
        folder = safe_path(self.root, folder_path)
        if not folder.exists():
            raise WikiStoreError(f"Folder not found: {folder_path}")

        try:
            if recursive:
                import shutil
                shutil.rmtree(folder)
            else:
                folder.rmdir()  # Only works if empty
        except Exception as e:
            raise WikiStoreError(f"Failed to delete folder: {e}") from e

    def get_index(self, folder_path: str = "") -> Dict[str, Dict[str, str]]:
        """Get folder index with document summaries.

        Returns:
            Dict mapping document names to their summary info
        """
        folder = safe_path(self.root, folder_path) if folder_path else self.root
        index: Dict[str, Dict[str, str]] = {}

        for doc_path in list_files(folder, "*.md"):
            try:
                content = read_file(doc_path)
                frontmatter, body = parse_frontmatter(content)

                # Get first non-empty paragraph as summary
                lines = body.strip().split('\n')
                summary = ""
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        summary = line[:200]  # First 200 chars
                        break

                index[doc_path.stem] = {
                    'title': frontmatter.get('title', doc_path.stem),
                    'summary': summary,
                    'modified': frontmatter.get('modified', '')
                }
            except Exception:
                continue

        return index

    # ── History tracking ────────────────────────────────────────────

    def _history_dir(self) -> Path:
        """Return path to .history directory, creating if needed."""
        path = self.root / ".history"
        ensure_directory(path)
        return path

    def _versions_dir(self) -> Path:
        """Return path to versions subdirectory, creating if needed."""
        path = self._history_dir() / "versions"
        ensure_directory(path)
        return path

    def _version_dir(self, doc_path: str) -> Path:
        """Return path to version directory for a document, creating if needed."""
        normalized = doc_path.replace("/", "_").replace(".md", "")
        path = self._versions_dir() / normalized
        ensure_directory(path)
        return path

    def save_version(self, path: str, operation: str, related: List[str] = None) -> DocumentVersion:
        """Save current document state as a new version.

        Args:
            path: Document path (with or without .md)
            operation: Operation type string (create, modify, delete, merge, split, rollback)
            related: Optional list of related document paths

        Returns:
            DocumentVersion that was saved
        """
        doc = None
        if self.document_exists(path):
            doc = self.read_document(path)

        versions = self.get_versions(path)
        next_version = len(versions) + 1

        version = DocumentVersion(
            version_id=DocumentVersion.create_id(),
            document_path=path,
            version_number=next_version,
            content=doc.content if doc else "",
            frontmatter=doc.frontmatter if doc else {},
            created_at=datetime.now(),
            created_by_operation=HistoryOperation(operation)
        )

        version_file = self._version_dir(path) / f"v{next_version}.json"
        write_file(version_file, version.model_dump_json(indent=2))

        entry = HistoryEntry(
            entry_id=HistoryEntry.create_id(),
            document_path=path,
            operation=HistoryOperation(operation),
            timestamp=datetime.now(),
            content_before=versions[-1].content if versions else None,
            content_after=doc.content if doc else None,
            metadata={"version_number": next_version},
            related_paths=related or []
        )

        self._append_history_entry(entry)

        return version

    def get_versions(self, path: str) -> List[DocumentVersion]:
        """Get all versions of a document, sorted by version number."""
        version_dir = self._version_dir(path)
        if not version_dir.exists():
            return []

        versions = []
        for version_file in sorted(version_dir.glob("v*.json")):
            try:
                data = json.loads(read_file(version_file))
                versions.append(DocumentVersion(**data))
            except Exception:
                continue

        return sorted(versions, key=lambda v: v.version_number)

    def get_version_content(self, path: str, version_number: int) -> str:
        """Get content of a specific version."""
        versions = self.get_versions(path)
        for v in versions:
            if v.version_number == version_number:
                return v.content
        raise WikiStoreError(f"Version {version_number} not found for {path}")

    def rollback_to_version(self, path: str, version_number: int) -> RollbackResult:
        """Rollback document to a specific version.

        Restores the content from the specified version and saves
        a new version with operation='rollback'.
        """
        try:
            versions = self.get_versions(path)
            target_version = None
            for v in versions:
                if v.version_number == version_number:
                    target_version = v
                    break

            if target_version is None:
                return RollbackResult(
                    success=False,
                    document_path=path,
                    version_restored=0,
                    error=f"Version {version_number} not found"
                )

            if not self.document_exists(path):
                doc = WikiDocument(
                    path=path,
                    title=target_version.frontmatter.get("title", path.split("/")[-1]),
                    content=target_version.content,
                    frontmatter=target_version.frontmatter,
                    created=datetime.now(),
                    modified=datetime.now(),
                    tags=target_version.frontmatter.get("tags", []),
                    category=target_version.frontmatter.get("category", ""),
                    related=target_version.frontmatter.get("related", [])
                )
            else:
                doc = self.read_document(path)
                doc.content = target_version.content
                doc.frontmatter = target_version.frontmatter
                doc.tags = target_version.frontmatter.get("tags", doc.tags)
                doc.category = target_version.frontmatter.get("category", doc.category)
                doc.related = target_version.frontmatter.get("related", doc.related)

            self.write_document(path, doc)
            self.save_version(path, "rollback")

            return RollbackResult(
                success=True,
                document_path=path,
                version_restored=version_number
            )
        except Exception as e:
            return RollbackResult(
                success=False,
                document_path=path,
                version_restored=0,
                error=str(e)
            )

    def get_history(self, path: str) -> List[HistoryEntry]:
        """Get history entries for a specific document."""
        index = self._load_history_index()
        return [entry for entry in index if entry.document_path == path]

    def get_recent_changes(self, limit: int = 20) -> List[HistoryEntry]:
        """Get most recent history entries across all documents."""
        index = self._load_history_index()
        sorted_entries = sorted(index, key=lambda e: e.timestamp, reverse=True)
        return sorted_entries[:limit]

    def _append_history_entry(self, entry: HistoryEntry) -> None:
        """Append a history entry to the index file."""
        index_path = self._history_dir() / "index.json"
        index = self._load_history_index()
        index.append(entry)
        data = [e.model_dump() for e in index]
        write_file(index_path, json.dumps(data, indent=2, default=str))

    def _load_history_index(self) -> List[HistoryEntry]:
        """Load history index from file."""
        index_path = self._history_dir() / "index.json"
        if not index_path.exists():
            return []
        try:
            data = json.loads(read_file(index_path))
            return [HistoryEntry(**e) for e in data]
        except Exception:
            return []
