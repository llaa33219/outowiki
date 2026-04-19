# API Reference: Plan Models

Plan models are used internally for complex operations like merging, splitting, and modifying documents.

## PlanType

Enum representing the type of plan.

```python
class PlanType(Enum):
    CREATE = "create"
    MODIFY = "modify"
    MERGE = "merge"
    SPLIT = "split"
    DELETE = "delete"
```

## Plan

Base class for all plans.

```python
@dataclass
class Plan:
    plan_type: PlanType
    rationale: str
    steps: List[PlanStep]
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `plan_type` | `PlanType` | Type of plan |
| `rationale` | `str` | Why this plan was created |
| `steps` | `list[PlanStep]` | Steps to execute |

## CreatePlan

A plan for creating new documents.

```python
@dataclass
class CreatePlan(Plan):
    plan_type: PlanType = PlanType.CREATE
    target_path: str = ""
    initial_content: str = ""
```

## ModifyPlan

A plan for modifying existing documents.

```python
@dataclass
class ModifyPlan(Plan):
    plan_type: PlanType = PlanType.MODIFY
    target_path: str = ""
    modifications: List[str] = field(default_factory=list)
```

## MergePlan

A plan for merging multiple documents into one.

```python
@dataclass
class MergePlan(Plan):
    plan_type: PlanType = PlanType.MERGE
    source_paths: List[str] = field(default_factory=list)
    target_path: str = ""
    merge_strategy: str = "append"
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `source_paths` | `list[str]` | Documents to merge |
| `target_path` | `str` | Destination document |
| `merge_strategy` | `str` | How to merge: "append", "interleave", "replace" |

## SplitPlan

A plan for splitting a document into multiple parts.

```python
@dataclass
class SplitPlan(Plan):
    plan_type: PlanType = PlanType.SPLIT
    source_path: str = ""
    split_points: List[int] = field(default_factory=list)
    target_paths: List[str] = field(default_factory=list)
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `source_path` | `str` | Document to split |
| `split_points` | `list[int]` | Character offsets for split points |
| `target_paths` | `list[str]` | Destination paths for parts |

## DeletePlan

A plan for deleting documents.

```python
@dataclass
class DeletePlan(Plan):
    plan_type: PlanType = PlanType.DELETE
    target_paths: List[str] = field(default_factory=list)
    remove_backlinks: bool = True
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `target_paths` | `list[str]` | Documents to delete |
| `remove_backlinks` | `bool` | Whether to clean up backlinks |
