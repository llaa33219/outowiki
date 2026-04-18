"""Markdown parsing utilities for OutoWiki.

Handles frontmatter parsing, wiki-link extraction, section parsing,
and token estimation for markdown documents.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import yaml


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    Returns a tuple of (frontmatter_dict, body_content).
    If no valid frontmatter is found, returns ({}, content).
    """
    content = content.strip()
    if not content.startswith("---"):
        return {}, content

    end_match = re.search(r"\n---\s*\n", content[3:])
    if end_match is None:
        return {}, content

    frontmatter_str = content[3 : 3 + end_match.start()]
    body = content[3 + end_match.end() :].strip()

    try:
        metadata = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError:
        return {}, content

    if not isinstance(metadata, dict):
        return {}, content

    return metadata, body


def create_frontmatter(metadata: dict[str, Any]) -> str:
    """Generate YAML frontmatter string from metadata dict.

    Standard fields: title, created, modified, tags, category, related.
    Missing fields are filled with sensible defaults.
    """
    now = datetime.now(timezone.utc).isoformat()

    fm: dict[str, Any] = {
        "title": metadata.get("title", ""),
        "created": metadata.get("created", now),
        "modified": metadata.get("modified", now),
        "tags": metadata.get("tags", []),
        "category": metadata.get("category", ""),
        "related": metadata.get("related", []),
    }

    for key, value in metadata.items():
        if key not in fm:
            fm[key] = value

    yaml_str = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str}---\n"


def extract_links(content: str) -> list[str]:
    """Extract [[wiki-style]] links from markdown content.

    Supports both [[target]] and [[target|display]] formats.
    Returns a deduplicated list of target paths.
    """
    pattern = r"\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]"
    matches = re.findall(pattern, content)

    seen: set[str] = set()
    result: list[str] = []
    for target in matches:
        target = target.strip()
        if target and target not in seen:
            seen.add(target)
            result.append(target)

    return result


def replace_links(content: str, replacements: dict[str, str]) -> str:
    """Replace wiki-link targets in content.

    replacements maps old_target -> new_target.
    Display text (if any) is preserved.
    """

    def _replacer(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        display = match.group(2)
        if target in replacements:
            new_target = replacements[target]
            if display:
                return f"[[{new_target}|{display}]]"
            return f"[[{new_target}]]"
        return match.group(0)

    pattern = r"\[\[([^\]|]+?)(\|([^\]]+?))?\]\]"
    return re.sub(pattern, _replacer, content)


def extract_sections(content: str) -> list[dict[str, str]]:
    """Parse markdown headers and their content sections.

    Returns list of dicts with keys: level (str), title (str), content (str).
    Content includes everything until the next header of same or higher level.
    """
    _, body = parse_frontmatter(content)

    lines = body.split("\n")
    sections: list[dict[str, str]] = []
    current_section: dict[str, str] | None = None
    current_lines: list[str] = []

    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

    for line in lines:
        header_match = header_pattern.match(line)
        if header_match:
            if current_section is not None:
                current_section["content"] = "\n".join(current_lines).strip()
                sections.append(current_section)

            level = str(len(header_match.group(1)))
            title = header_match.group(2).strip()
            current_section = {"level": level, "title": title, "content": ""}
            current_lines = []
        else:
            current_lines.append(line)

    if current_section is not None:
        current_section["content"] = "\n".join(current_lines).strip()
        sections.append(current_section)

    return sections


def estimate_tokens(content: str) -> int:
    """Estimate token count for content.

    Uses the heuristic of ~4 characters per token.
    """
    return len(content) // 4
