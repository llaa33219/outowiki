"""Content models for OutoWiki - raw input and wiki document structures."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RawContent(BaseModel):
    """Raw input content before processing by the wiki system.

    Represents unstructured input from various sources such as
    conversation logs, agent reasoning, external documents, or
    structured data.
    """

    content: str
    content_type: Literal["conversation", "agent_internal", "external", "structured"]
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class WikiDocument(BaseModel):
    """A wiki document stored in the knowledge base.

    Represents a fully processed markdown document with frontmatter,
    backlinks, and metadata. Each document lives at a specific path
    within the wiki's folder-based hierarchy.
    """

    path: str
    title: str
    content: str
    frontmatter: Dict[str, Any]
    backlinks: List[str] = []
    created: datetime
    modified: datetime
    tags: List[str] = []
    category: str
    related: List[str] = []


class DocumentMetadata(BaseModel):
    """Metadata extracted from or intended for a wiki document's frontmatter.

    Used when creating or updating documents to specify classification,
    tagging, and cross-referencing information.
    """

    title: str
    tags: List[str] = []
    category: str
    related: List[str] = []
    custom: Dict[str, Any] = {}
