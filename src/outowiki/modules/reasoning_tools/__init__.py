"""Reasoning tools for agent loop."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...models.analysis import AnalysisResult, IntentAnalysis
from ...models.content import DocumentGeneration, SummaryGeneration
from ...models.plans import PlanResponse
from ..tools import ToolDefinition


class AnalyzeContentInput(BaseModel):
    content: str = Field(description="Raw content to analyze")
    content_type: str = Field(
        default="conversation",
        description="Type of content: conversation, agent_internal, external, structured"
    )


class AnalyzeContentOutput(AnalysisResult):
    pass


class CreatePlanInput(BaseModel):
    analysis: dict[str, Any] = Field(description="Analysis result from analyze_content")
    affected_docs: list[str] = Field(default_factory=list, description="Paths of affected documents")
    doc_summaries: dict[str, str] = Field(default_factory=dict, description="Document summaries")


class CreatePlanOutput(PlanResponse):
    pass


class GenerateDocumentInput(BaseModel):
    content: str = Field(description="Content to generate document from")
    title: str = Field(description="Document title")
    category: str = Field(default="", description="Document category")
    tags: list[str] = Field(default_factory=list, description="Document tags")
    related: list[str] = Field(default_factory=list, description="Related document paths")


class GenerateDocumentOutput(DocumentGeneration):
    pass


class GenerateSummaryInput(BaseModel):
    content: str = Field(description="Content to summarize")


class GenerateSummaryOutput(SummaryGeneration):
    pass


class AnalyzeSearchIntentInput(BaseModel):
    query: str = Field(description="Search query")
    context: str = Field(default="General search", description="Search context")
    categories: list[str] = Field(default_factory=list, description="Available categories")


class AnalyzeSearchIntentOutput(IntentAnalysis):
    pass


def create_reasoning_tools() -> list[ToolDefinition]:
    """Create reasoning tools for structured LLM output.
    
    These tools are "called" by the LLM to structure its own analysis
    output into Pydantic schemas. The handler is an identity function -
    the real work is the schema validation.
    """
    
    def analyze_content(input: AnalyzeContentInput) -> AnalyzeContentOutput:
        return AnalyzeContentOutput(
            information_type="knowledge",
            specific_content=input.content[:200],
            suggested_action="create",
            target_documents=[],
            confidence=0.8,
        )
    
    def create_plan(input: CreatePlanInput) -> CreatePlanOutput:
        return CreatePlanOutput(plans=[])
    
    def generate_document(input: GenerateDocumentInput) -> GenerateDocumentOutput:
        return GenerateDocumentOutput(content=input.content)
    
    def generate_summary(input: GenerateSummaryInput) -> GenerateSummaryOutput:
        return GenerateSummaryOutput(summary=input.content[:100])
    
    def analyze_search_intent(input: AnalyzeSearchIntentInput) -> AnalyzeSearchIntentOutput:
        return AnalyzeSearchIntentOutput(
            information_type="knowledge",
            specificity_level="general",
            temporal_interest="all_time",
            exploration_start="root",
            confidence_requirement="medium",
        )
    
    return [
        ToolDefinition(
            name="analyze_content",
            description="Analyze raw content and extract structured information",
            input_model=AnalyzeContentInput,
            handler=analyze_content,
        ),
        ToolDefinition(
            name="create_plan",
            description="Create modification plans based on analysis",
            input_model=CreatePlanInput,
            handler=create_plan,
        ),
        ToolDefinition(
            name="generate_document",
            description="Generate document content from raw content",
            input_model=GenerateDocumentInput,
            handler=generate_document,
        ),
        ToolDefinition(
            name="generate_summary",
            description="Generate a summary of content",
            input_model=GenerateSummaryInput,
            handler=generate_summary,
        ),
        ToolDefinition(
            name="analyze_search_intent",
            description="Analyze search query intent",
            input_model=AnalyzeSearchIntentInput,
            handler=analyze_search_intent,
        ),
    ]
