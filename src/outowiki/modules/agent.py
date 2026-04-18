"""Internal agent for LLM-based information processing."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from ..providers.base import LLMProvider
from ..models.analysis import AnalysisResult, IntentAnalysis
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
from ..core.exceptions import ProviderError

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

    def __init__(self, provider: LLMProvider):
        """Initialize internal agent.

        Args:
            provider: LLM provider for completions
        """
        self.provider = provider

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
            context: Additional context (categories, recent_docs, etc.)

        Returns:
            AnalysisResult with extracted information

        Raises:
            ProviderError: If LLM call fails
        """
        ctx = context or {}

        # Select appropriate prompt based on content type
        if content_type == "conversation":
            prompt = CONVERSATION_ANALYSIS_PROMPT.format(
                content=content,
                context=ctx.get('context', 'General conversation')
            )
        elif content_type == "agent_internal":
            prompt = LEARNING_ANALYSIS_PROMPT.format(
                content=content,
                context=ctx.get('context', 'Agent internal'),
                previous_attempts=ctx.get('previous_attempts', 'None')
            )
        else:
            prompt = ANALYSIS_PROMPT.format(
                content=content,
                categories=ctx.get('categories', []),
                recent_docs=ctx.get('recent_docs', [])
            )

        return self._call_with_schema(prompt, AnalysisResult)

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
        if analysis.suggested_action == PlanType.MERGE and merge_docs:
            prompt = MERGE_PLANNING_PROMPT.format(
                documents_json=json.dumps(merge_docs, indent=2),
                reason=analysis.specific_content
            )
        elif analysis.suggested_action == PlanType.SPLIT and split_doc:
            prompt = SPLIT_PLANNING_PROMPT.format(
                document_json=json.dumps(split_doc, indent=2),
                reason=analysis.specific_content
            )
        else:
            prompt = PLANNING_PROMPT.format(
                analysis_json=analysis.model_dump_json(indent=2),
                affected_docs=list(affected_docs.keys()) if affected_docs else [],
                doc_summaries=json.dumps(affected_docs or {}, indent=2)
            )

        response = self.provider.complete(prompt)

        # Parse response as list of plans
        try:
            data = json.loads(response)
            if isinstance(data, dict):
                data = [data]

            plans = []
            for plan_data in data:
                plan_type = plan_data.get('plan_type', 'create')
                if plan_type in ('create', 'CREATE'):
                    from ..models.plans import CreatePlan
                    plans.append(CreatePlan(**plan_data))
                elif plan_type in ('modify', 'MODIFY'):
                    from ..models.plans import ModifyPlan
                    plans.append(ModifyPlan(**plan_data))
                elif plan_type in ('merge', 'MERGE'):
                    from ..models.plans import MergePlan
                    plans.append(MergePlan(**plan_data))
                elif plan_type in ('split', 'SPLIT'):
                    from ..models.plans import SplitPlan
                    plans.append(SplitPlan(**plan_data))
                elif plan_type in ('delete', 'DELETE'):
                    from ..models.plans import DeletePlan
                    plans.append(DeletePlan(**plan_data))

            return plans
        except (json.JSONDecodeError, ValidationError) as e:
            raise ProviderError(f"Failed to parse plans: {e}") from e

    def generate_document(
        self,
        content: str,
        title: str,
        category: str,
        tags: List[str],
        related: List[str]
    ) -> str:
        """Generate markdown document content.

        Args:
            content: Raw content to document
            title: Document title
            category: Document category path
            tags: Document tags
            related: Related document paths

        Returns:
            Generated markdown content (without frontmatter)

        Raises:
            ProviderError: If LLM call fails
        """
        prompt = DOCUMENT_GENERATION_PROMPT.format(
            content=content,
            title=title,
            category=category,
            tags=tags,
            related=related
        )

        return self.provider.complete(prompt)

    def generate_summary(self, content: str) -> str:
        """Generate a brief summary of content.

        Args:
            content: Content to summarize

        Returns:
            Summary text (under 200 tokens)
        """
        prompt = SUMMARY_GENERATION_PROMPT.format(content=content)
        return self.provider.complete(prompt, max_tokens=300)

    def _call_with_schema(self, prompt: str, schema: Type[T]) -> T:
        """Call LLM with schema validation.

        Args:
            prompt: Prompt to send
            schema: Pydantic model for response validation

        Returns:
            Validated instance of schema
        """
        return self.provider.complete_with_schema(prompt, schema)
