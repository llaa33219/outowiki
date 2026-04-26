"""Validation utilities for wiki documents."""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath


def title_to_filename(title: str) -> str:
    """Convert a document title to its expected filename (without .md).

    Examples:
        "Python Classes" -> "python_classes"
        "React Native Camera" -> "react_native_camera"
        "Alice's Preferences" -> "alices_preferences"
    """
    normalized = unicodedata.normalize('NFKD', title).lower()
    normalized = re.sub(r'[\s\-]+', '_', normalized)
    normalized = re.sub(r'[^a-z0-9_]', '', normalized)
    normalized = re.sub(r'_+', '_', normalized)
    return normalized.strip('_')


def filename_to_title(filename: str) -> str:
    """Convert a filename (without .md) to its expected title.

    Examples:
        "python_classes" -> "Python Classes"
        "react_native_camera" -> "React Native Camera"
    """
    if filename.endswith('.md'):
        filename = filename[:-3]
    return filename.replace('_', ' ').title()


def is_english(text: str) -> bool:
    """Check if text contains only English characters (ASCII letters, digits, common punctuation)."""
    if not text:
        return True
    pattern = r'^[a-zA-Z0-9\s\-_.,!?()\'\":;/@#$%^&*+=<>[\]{}|\\~`]+$'
    return bool(re.match(pattern, text))


def validate_title_english(title: str) -> tuple[bool, str]:
    """Validate that a title is in English. Returns (is_valid, error_message)."""
    if not title or is_english(title):
        return True, ""
    return False, f"Title must be in English: '{title}'"


def validate_tags_english(tags: list[str]) -> tuple[bool, str]:
    """Validate that all tags are in English. Returns (is_valid, error_message)."""
    for tag in tags:
        if not is_english(tag):
            return False, f"Tag must be in English: '{tag}'"
    return True, ""


def validate_title_filename_consistency(title: str, path: str) -> tuple[bool, str]:
    """Validate that title matches the filename in the path. Returns (is_valid, error_message)."""
    if not title or not path:
        return True, ""

    path_obj = PurePosixPath(path)
    filename = path_obj.name
    if filename.endswith('.md'):
        filename = filename[:-3]

    expected_filename = title_to_filename(title)

    if filename.lower() != expected_filename.lower():
        return False, (
            f"Title '{title}' does not match filename '{filename}'. "
            f"Expected filename: '{expected_filename}'"
        )
    return True, ""


def validate_document(
    title: str,
    path: str,
    tags: list[str] | None = None
) -> tuple[bool, list[str]]:
    """Validate a document's title, path, and tags. Returns (is_valid, list_of_errors)."""
    errors = []

    valid, msg = validate_title_english(title)
    if not valid:
        errors.append(msg)

    if tags:
        valid, msg = validate_tags_english(tags)
        if not valid:
            errors.append(msg)

    valid, msg = validate_title_filename_consistency(title, path)
    if not valid:
        errors.append(msg)

    return len(errors) == 0, errors
