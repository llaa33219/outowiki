# API Reference: Plan Models

Plan models are used internally for complex operations like merging, splitting, and modifying documents. They are now returned via tool calling using discriminated unions.

## PlanType

Enum representing the type of plan.

```python
from enum import Enum

class PlanType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    MERGE = "merge"
    SPLIT = "split"
    DELETE = "delete"
```

## Plan

Base class for all plans.

```python
from pydantic import BaseModel

class Plan(BaseModel):
    plan_type: PlanType
    target_path: str
    reason: str
    priority: int = 0
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `plan_type` | `PlanType` | Type of plan |
| `target_path` | `str` | Target document path |
| `reason` | `str` | Why this plan was created |
| `priority` | `int` | Execution priority (0 = normal) |

## CreatePlan

A plan for creating new documents.

```python
from typing import List
from outowiki.models.content import DocumentMetadata

class CreatePlan(Plan):
    plan_type: Literal[PlanType.CREATE] = PlanType.CREATE
    content: str
    metadata: DocumentMetadata
    backlinks_to_add: List[str] = []
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Document content |
| `metadata` | `DocumentMetadata` | Document metadata |
| `backlinks_to_add` | `list[str]` | Backlinks to create |

## ModifyPlan

A plan for modifying existing documents.

```python
from typing import Any, Dict

class ModifyPlan(Plan):
    plan_type: Literal[PlanType.MODIFY] = PlanType.MODIFY
    modifications: List[Dict[str, Any]]
    backlinks_to_update: List[str] = []
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `modifications` | `list[dict]` | Modification operations |
| `backlinks_to_update` | `list[str]` | Backlinks to update |

## MergePlan

A plan for merging multiple documents into one.

```python
class MergePlan(Plan):
    plan_type: Literal[PlanType.MERGE] = PlanType.MERGE
    source_paths: List[str]
    merged_content: str
    redirect_sources: bool = True
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `source_paths` | `list[str]` | Documents to merge |
| `merged_content` | `str` | Resulting merged content |
| `redirect_sources` | `bool` | Create redirects for sources |

## SplitPlan

A plan for splitting a document into multiple parts.

```python
class SplitPlan(Plan):
    plan_type: Literal[PlanType.SPLIT] = PlanType.SPLIT
    sections_to_split: List[Dict[str, str]]
    summary_for_main: str
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sections_to_split` | `list[dict]` | Sections to extract |
| `summary_for_main` | `str` | Summary for main document |

## DeletePlan

A plan for deleting documents.

```python
from typing import Optional

class DeletePlan(Plan):
    plan_type: Literal[PlanType.DELETE] = PlanType.DELETE
    remove_backlinks: bool = True
    redirect_to: Optional[str] = None
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `remove_backlinks` | `bool` | Clean up backlinks |
| `redirect_to` | `str \| None` | Redirect target |

## PlanResponse

Response wrapper used by tool calling to return structured plan data.

```python
from typing import Annotated, Union
from pydantic import Field

PlanUnion = Annotated[
    Union[CreatePlan, ModifyPlan, MergePlan, SplitPlan, DeletePlan],
    Field(discriminator="plan_type")
]

class PlanResponse(BaseModel):
    plans: List[PlanUnion]
```

This allows the LLM to return multiple plans of different types in a single tool call.
