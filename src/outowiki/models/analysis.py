"""Analysis models for OutoWiki - information and intent analysis results.

Defines the structures produced by the analysis pipeline stages:
information analysis (for recording) and intent analysis (for search).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from outowiki.models.plans import PlanType


class AnalysisResult(BaseModel):
    """Result of analyzing raw input content.

    Produced by the recording pipeline's analysis stage, this captures
    what the input contains, how important it is, and what action
    should be taken in the wiki.
    """

    information_type: str
    key_topic: str
    specific_content: str
    existing_relations: List[str] = []
    temporal_range: Optional[str] = None
    confidence_score: float = Field(ge=0.0, le=1.0)
    importance_score: float = Field(ge=0.0, le=1.0)
    suggested_action: PlanType
    target_documents: List[str] = []


class IntentAnalysis(BaseModel):
    """Result of analyzing a search query's intent.

    Produced by the search pipeline's intent analysis stage, this
    guides the document exploration by specifying what kind of
    information is needed and where to look for it.
    """

    information_type: str
    specificity_level: Literal["very_specific", "specific", "general", "very_general"]
    temporal_interest: Literal["recent", "all_time", "specific_period"]
    exploration_start: str
    confidence_requirement: Literal["high", "medium", "low"]
