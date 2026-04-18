"""Filesystem utilities for wiki directory and file management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def safe_path(base: Path, target: str) -> Path:
    """Validate target path doesn't escape base directory.

    Resolves the target against base and ensures the result is within base.
    Raises ValueError if path traversal is detected.
    """
    base = base.resolve()
    clean_target = target.lstrip("/")
    resolved = (base / clean_target).resolve()

    if not str(resolved).startswith(str(base) + os.sep) and resolved != base:
        raise ValueError(f"Path traversal detected: {target} escapes {base}")

    return resolved


def ensure_directory(path: Path) -> None:
    """Create directory and all parent directories if they don't exist."""
    path.mkdir(parents=True, exist_ok=True)


def read_file(path: Path) -> str:
    """Read file content with UTF-8 encoding.

    Handles encoding errors by replacing undecodable bytes.
    """
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(path: Path, content: str, atomic: bool = True) -> None:
    """Write content to file with UTF-8 encoding.

    If atomic=True, writes to a temp file first then renames to prevent corruption.
    """
    ensure_directory(path.parent)

    if atomic:
        fd, tmp_path = tempfile.mkstemp(
            dir=str(path.parent), prefix=".tmp_", suffix=path.suffix
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    else:
        path.write_text(content, encoding="utf-8")


def delete_file(path: Path) -> None:
    """Delete file. Raises IsADirectoryError if path is a directory."""
    if path.is_dir():
        raise IsADirectoryError(f"Expected a file, got directory: {path}")
    path.unlink(missing_ok=True)


def list_files(folder: Path, pattern: str = "*.md") -> list[Path]:
    """List files matching glob pattern, sorted by name."""
    if not folder.is_dir():
        return []
    return sorted(folder.glob(pattern))


def list_folders(folder: Path) -> list[Path]:
    """List subdirectories, sorted by name."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir())


def relative_to(base: Path, target: Path) -> str:
    """Get relative path string from base to target.

    Returns forward-slash separated path for cross-platform compatibility.
    """
    return target.resolve().relative_to(base.resolve()).as_posix()
