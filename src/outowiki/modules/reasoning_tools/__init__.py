"""Reasoning tools for agent loop."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from ...models.analysis import AnalysisResult, IntentAnalysis
from ...models.content import DocumentGeneration, SummaryGeneration
from ...models.plans import PlanResponse, PlanType
from ...providers.base import LLMProvider
from ..tools import ToolDefinition

logger = logging.getLogger(__name__)


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


def create_reasoning_tools(provider: LLMProvider | None = None) -> list[ToolDefinition]:
    """Create reasoning tools for structured LLM output.
    
    When provider is provided, tools will call the LLM to generate analysis.
    When provider is None, tools return stub values (for testing).
    """
    
    def analyze_content(input: AnalyzeContentInput) -> AnalyzeContentOutput:
        if provider is None:
            return AnalyzeContentOutput(
                information_type="knowledge",
                key_topic="general",
                specific_content=input.content[:200],
                confidence_score=0.8,
                importance_score=0.5,
                suggested_action=PlanType.CREATE,
                target_documents=[],
            )
        
        prompt = f"""Analyze this content and extract structured information.

Content type: {input.content_type}
Content:
{input.content[:2000]}

Extract:
1. information_type: What type of information is this? (conversation, agent_internal, external, structured, knowledge, user, tool)
2. key_topic: The main topic or concept
3. specific_content: Key facts and details
4. confidence_score: How confident are you in this analysis? (0.0-1.0)
5. importance_score: How important is this information? (0.0-1.0)
6. suggested_action: What should be done with this information? (CREATE, MODIFY, MERGE, SPLIT, DELETE, NOOP)
7. target_documents: Paths of related existing documents (if any)

Respond with JSON matching the schema."""
        
        try:
            return provider.complete_with_schema(prompt, AnalyzeContentOutput)
        except Exception as e:
            logger.error(f"analyze_content LLM call failed: {e}")
            return AnalyzeContentOutput(
                information_type="knowledge",
                key_topic="general",
                specific_content=input.content[:200],
                confidence_score=0.5,
                importance_score=0.5,
                suggested_action=PlanType.CREATE,
                target_documents=[],
            )
    
    def create_plan(input: CreatePlanInput) -> CreatePlanOutput:
        if provider is None:
            return CreatePlanOutput(plans=[])
        
        prompt = f"""Based on the analysis and affected documents, create modification plans.

Analysis:
{input.analysis}

Affected documents: {input.affected_docs}
Document summaries: {input.doc_summaries}

Create plans to record this information in the wiki. Consider:
- CREATE: New document for new information
- MODIFY: Update existing document
- MERGE: Combine related documents
- SPLIT: Break large document into parts
- DELETE: Remove outdated information

Respond with JSON matching the schema."""
        
        try:
            return provider.complete_with_schema(prompt, CreatePlanOutput)
        except Exception as e:
            logger.error(f"create_plan LLM call failed: {e}")
            return CreatePlanOutput(plans=[])
    
    def generate_document(input: GenerateDocumentInput) -> GenerateDocumentOutput:
        if provider is None:
            return GenerateDocumentOutput(content=input.content)
        
        prompt = f"""Generate a well-structured wiki document from this content.

Title: {input.title}
Category: {input.category}
Tags: {input.tags}
Related documents: {input.related}

Raw content:
{input.content[:3000]}

Generate a proper markdown document with:
- Clear heading structure
- Well-organized sections
- Relevant details from the content
- Links to related documents using [[path]] syntax

Do NOT include frontmatter (---) - just the markdown content.
Respond with JSON matching the schema."""
        
        try:
            return provider.complete_with_schema(prompt, GenerateDocumentOutput)
        except Exception as e:
            logger.error(f"generate_document LLM call failed: {e}")
            return GenerateDocumentOutput(content=input.content)
    
    def generate_summary(input: GenerateSummaryInput) -> GenerateSummaryOutput:
        if provider is None:
            return GenerateSummaryOutput(summary=input.content[:100])
        
        prompt = f"""Generate a concise summary of this content.

Content:
{input.content[:2000]}

Create a brief summary (1-3 sentences) that captures the key points.
Respond with JSON matching the schema."""
        
        try:
            return provider.complete_with_schema(prompt, GenerateSummaryOutput)
        except Exception as e:
            logger.error(f"generate_summary LLM call failed: {e}")
            return GenerateSummaryOutput(summary=input.content[:100])
    
    def analyze_search_intent(input: AnalyzeSearchIntentInput) -> AnalyzeSearchIntentOutput:
        if provider is None:
            return AnalyzeSearchIntentOutput(
                information_type="knowledge",
                specificity_level="general",
                temporal_interest="all_time",
                exploration_start="root",
                confidence_requirement="medium",
            )
        
        categories_str = ", ".join(input.categories[:20]) if input.categories else "none available"
        
        prompt = f"""Analyze this search query and determine the search strategy.

Query: {input.query}
Context: {input.context}
Available categories: {categories_str}

Determine:
1. information_type: What type of information is being sought? (user, tool, knowledge, history, agent)
2. specificity_level: How specific is the query? (very_specific, specific, general, very_general)
3. temporal_interest: Time relevance? (recent, all_time, specific_period)
4. exploration_start: Which category to start exploring? (folder path or 'root')
5. confidence_requirement: How confident must results be? (high, medium, low)

Respond with JSON matching the schema."""
        
        try:
            return provider.complete_with_schema(prompt, AnalyzeSearchIntentOutput)
        except Exception as e:
            logger.error(f"analyze_search_intent LLM call failed: {e}")
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
