"""Prompt templates for analysis, planning, and content generation."""

from outowiki.prompts.analysis import (
    ANALYSIS_PROMPT,
    CONVERSATION_ANALYSIS_PROMPT,
    LEARNING_ANALYSIS_PROMPT,
)
from outowiki.prompts.planning import (
    PLANNING_PROMPT,
    MERGE_PLANNING_PROMPT,
    SPLIT_PLANNING_PROMPT,
)
from outowiki.prompts.generation import (
    DOCUMENT_GENERATION_PROMPT,
    SUMMARY_GENERATION_PROMPT,
)

__all__ = [
    "ANALYSIS_PROMPT",
    "CONVERSATION_ANALYSIS_PROMPT",
    "LEARNING_ANALYSIS_PROMPT",
    "PLANNING_PROMPT",
    "MERGE_PLANNING_PROMPT",
    "SPLIT_PLANNING_PROMPT",
    "DOCUMENT_GENERATION_PROMPT",
    "SUMMARY_GENERATION_PROMPT",
]
