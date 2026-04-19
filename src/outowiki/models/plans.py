"""Plan models for OutoWiki - document modification plans.

Defines the plan types used by the recording pipeline to describe
how wiki documents should be created, modified, merged, split, or deleted.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from outowiki.models.content import DocumentMetadata


class PlanType(str, Enum):
    """Enumeration of possible document modification plan types."""

    CREATE = "create"
    MODIFY = "modify"
    MERGE = "merge"
    SPLIT = "split"
    DELETE = "delete"


class Plan(BaseModel):
    """Base class for all document modification plans.

    Each plan targets a specific wiki path and carries a reason
    explaining why the modification is needed.
    """

    plan_type: PlanType
    target_path: str
    reason: str
    priority: int = 0


class CreatePlan(Plan):
    """Plan to create a new wiki document.

    Contains the full content and metadata for the new document,
    plus any backlinks that should be added to existing documents.
    """

    plan_type: Literal[PlanType.CREATE] = PlanType.CREATE
    content: str
    metadata: DocumentMetadata
    backlinks_to_add: List[str] = []


class ModifyPlan(Plan):
    """Plan to modify an existing wiki document.

    Each modification specifies a section, operation type, and
    the content to apply. Backlinks can be updated as part of
    the modification.
    """

    plan_type: Literal[PlanType.MODIFY] = PlanType.MODIFY
    modifications: List[Dict[str, Any]]
    backlinks_to_update: List[str] = []


class MergePlan(Plan):
    """Plan to merge multiple source documents into one.

    The merged content replaces the target document, and source
    documents can optionally be replaced with redirects.
    """

    plan_type: Literal[PlanType.MERGE] = PlanType.MERGE
    source_paths: List[str]
    merged_content: str
    redirect_sources: bool = True


class SplitPlan(Plan):
    """Plan to split a document into multiple sub-documents.

    Each section to split gets a new path. The main document
    receives a summary replacing the extracted sections.
    """

    plan_type: Literal[PlanType.SPLIT] = PlanType.SPLIT
    sections_to_split: List[Dict[str, str]]
    summary_for_main: str


class DeletePlan(Plan):
    """Plan to delete a wiki document.

    Optionally removes backlinks from referencing documents and
    can set up a redirect to a replacement document.
    """

    plan_type: Literal[PlanType.DELETE] = PlanType.DELETE
    remove_backlinks: bool = True
    redirect_to: Optional[str] = None


PlanUnion = Annotated[
    Union[CreatePlan, ModifyPlan, MergePlan, SplitPlan, DeletePlan],
    Field(discriminator="plan_type")
]


class PlanResponse(BaseModel):
    """Response containing a list of plans.

    Used by tool calling to return structured plan data.
    """

    plans: List[PlanUnion]
