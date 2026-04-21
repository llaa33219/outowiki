"""Internal agent for LLM-based information processing."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from ..providers.base import LLMProvider
from ..models.analysis import AnalysisResult
from ..models.content import DocumentGeneration, SummaryGeneration
from ..models.plans import Plan, PlanType
from ..prompts import (
    ANALYSIS_PROMPT,
    CONVERSATION_ANALYSIS_PROMPT,
    LEARNING_ANALYSIS_PROMPT,
    PLANNING_PROMPT,
    MERGE_PLANNING_PROMPT,
    SPLIT_PLANNING_PROMPT,
    DOCUMENT_GENERATION_PROMPT,
    SUMMARY_GENERATION_PROMPT
)

T = TypeVar('T', bound=BaseModel)


class InternalAgent:
    """LLM-based agent for information processing.

    Handles analysis, planning, and document generation by
    orchestrating calls to the configured LLM provider.

    Example:
        provider = OpenAIProvider(api_key="sk-...", model="gpt-4")
        agent = InternalAgent(provider)
        analysis = agent.analyze(content, context={"categories": [...]})
    """

    def __init__(self, provider: LLMProvider, logger: Optional[logging.Logger] = None):
        """Initialize internal agent.

        Args:
            provider: LLM provider for completions
            logger: Optional logger for debug output
        """
        self.provider = provider
        self.logger = logger or logging.getLogger(__name__)

    def analyze(
        self,
        content: str,
        content_type: str = "conversation",
        context: Optional[Dict[str, Any]] = None
    ) -> AnalysisResult:
        """Analyze raw content and extract structured information.

        Args:
            content: Raw input content
            content_type: Type of content (conversation, agent_internal, external, structured)
            context: Additional context (categories, recent_docs, existing_doc_path, existing_doc_content, etc.)

        Returns:
            AnalysisResult with extracted information

        Raises:
            ProviderError: If LLM call fails
        """
        self.logger.debug(f"Analyzing content: {content[:100]}...")
        self.logger.debug(f"Content type: {content_type}")
        
        ctx = context or {}

        existing_doc_section = ""
        if ctx.get('existing_doc_path'):
            existing_doc_section = f"""
EXISTING DOCUMENT FOUND:
- Path: {ctx['existing_doc_path']}
- Content preview: {ctx.get('existing_doc_content', '')[:1000]}

IMPORTANT: A related document already exists. Consider MODIFY instead of CREATE if the new information should be added to this existing document.
"""

        # Select appropriate prompt based on content type
        if content_type == "conversation":
            prompt = CONVERSATION_ANALYSIS_PROMPT.format(
                content=content,
                context=ctx.get('context', 'General conversation'),
                categories=ctx.get('categories', []),
                recent_docs=ctx.get('recent_docs', [])
            )
        elif content_type == "agent_internal":
            prompt = LEARNING_ANALYSIS_PROMPT.format(
                content=content,
                context=ctx.get('context', 'Agent internal'),
                previous_attempts=ctx.get('previous_attempts', 'None'),
                categories=ctx.get('categories', []),
                recent_docs=ctx.get('recent_docs', [])
            )
        else:
            prompt = ANALYSIS_PROMPT.format(
                content=content,
                categories=ctx.get('categories', []),
                recent_docs=ctx.get('recent_docs', []),
                existing_doc_section=existing_doc_section
            )

        self.logger.debug(f"Using prompt type: {content_type}")
        analysis = self._call_with_schema(prompt, AnalysisResult)
        self.logger.debug(f"Analysis completed: {analysis}")
        return analysis

    def plan(
        self,
        analysis: AnalysisResult,
        affected_docs: Optional[Dict[str, str]] = None,
        merge_docs: Optional[List[Dict[str, Any]]] = None,
        split_doc: Optional[Dict[str, Any]] = None
    ) -> List[Plan]:
        """Create modification plans based on analysis.

        Args:
            analysis: Analysis result from analyze()
            affected_docs: Dict of path -> summary for affected documents
            merge_docs: Documents to merge (for MERGE action)
            split_doc: Document to split (for SPLIT action)

        Returns:
            List of Plan objects to execute

        Raises:
            ProviderError: If LLM call fails
        """
        self.logger.debug(f"Creating plans for action: {analysis.suggested_action}")
        self.logger.debug(f"Affected documents: {list(affected_docs.keys()) if affected_docs else []}")
        
        if analysis.suggested_action == PlanType.MERGE and merge_docs:
            prompt = MERGE_PLANNING_PROMPT.format(
                documents_json=json.dumps(merge_docs, indent=2),
                reason=analysis.specific_content
            )
            self.logger.debug("Using merge planning prompt")
        elif analysis.suggested_action == PlanType.SPLIT and split_doc:
            prompt = SPLIT_PLANNING_PROMPT.format(
                document_json=json.dumps(split_doc, indent=2),
                reason=analysis.specific_content
            )
            self.logger.debug("Using split planning prompt")
        else:
            prompt = PLANNING_PROMPT.format(
                analysis_json=analysis.model_dump_json(indent=2),
                affected_docs=list(affected_docs.keys()) if affected_docs else [],
                doc_summaries=json.dumps(affected_docs or {}, indent=2)
            )
            self.logger.debug("Using standard planning prompt")

        self.logger.debug("Calling LLM for plan generation...")
        from ..models.plans import PlanResponse
        plan_response = self._call_with_schema(prompt, PlanResponse)
        
        for plan in plan_response.plans:
            if hasattr(plan, 'metadata') and plan.metadata:
                if not plan.metadata.title:
                    self.logger.warning("LLM generated plan without title. Retrying with explicit instruction.")
                    prompt += "\n\nIMPORTANT: You MUST provide a title in metadata.title for EVERY plan. Title is REQUIRED."
                    plan_response = self._call_with_schema(prompt, PlanResponse)
                    break
        
        self.logger.debug(f"Generated {len(plan_response.plans)} plans")
        return list(plan_response.plans)

    def generate_document(
        self,
        content: str,
        title: str,
        category: str,
        tags: List[str],
        related: List[str]
    ) -> str:
        self.logger.debug(f"Generating document: {title}")
        self.logger.debug(f"Category: {category}, Tags: {tags}, Related: {related}")
        
        prompt = DOCUMENT_GENERATION_PROMPT.format(
            content=content,
            title=title,
            category=category,
            tags=tags,
            related=related
        )

        self.logger.debug("Calling LLM for document generation...")
        result = self._call_with_schema(prompt, DocumentGeneration)
        self.logger.debug(f"Generated document length: {len(result.content)} characters")
        return result.content

    def generate_summary(self, content: str) -> str:
        self.logger.debug(f"Generating summary for content: {content[:50]}...")
        
        prompt = SUMMARY_GENERATION_PROMPT.format(content=content)
        result = self._call_with_schema(prompt, SummaryGeneration)
        
        self.logger.debug(f"Generated summary: {result.summary[:50]}...")
        return result.summary

    def _call_with_schema(self, prompt: str, schema: Type[T]) -> T:
        self.logger.debug(f"Calling LLM with schema: {schema.__name__}")
        result = self.provider.complete_with_schema(prompt, schema)
        self.logger.debug(f"Schema validation successful: {schema.__name__}")
        return result
