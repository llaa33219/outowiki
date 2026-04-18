"""History tracking models for OutoWiki - immutable records of document operations."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HistoryOperation(str, Enum):
    """Types of operations tracked in document history."""

    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    MERGE = "merge"
    SPLIT = "split"
    ROLLBACK = "rollback"


class HistoryEntry(BaseModel):
    """Immutable record of a single document operation.

    History entries are never modified after creation. They provide
    a full audit trail of every change made to wiki documents.
    """

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_path: str
    operation: HistoryOperation
    timestamp: datetime = Field(default_factory=datetime.now)
    content_before: Optional[str] = None
    content_after: Optional[str] = None
    metadata: Dict[str, Any] = {}
    related_paths: List[str] = []

    @staticmethod
    def create_id() -> str:
        """Generate a UUID-based entry ID."""
        return str(uuid.uuid4())


class DocumentVersion(BaseModel):
    """Snapshot of a document at a specific point in time.

    Captures the full content and frontmatter of a document so it
    can be restored during a rollback operation.
    """

    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_path: str
    version_number: int
    content: str
    frontmatter: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)
    created_by_operation: HistoryOperation

    @staticmethod
    def create_id() -> str:
        """Generate a UUID-based version ID."""
        return str(uuid.uuid4())


class RollbackResult(BaseModel):
    """Outcome of a rollback operation on a document.

    Indicates whether the rollback succeeded and, if so, which
    version number was restored.
    """

    success: bool
    document_path: str
    version_restored: int
    error: Optional[str] = None
