"""OutoWiki - AI Agent Knowledge Management Wiki.

A Python library for managing AI agent knowledge using
wiki-based markdown storage with LLM-powered processing.

Quick Start:
    from outowiki import OutoWiki, WikiConfig

    config = WikiConfig(
        provider="openai",
        api_key="sk-...",
        model="gpt-4",
        wiki_path="./my_wiki"
    )

    wiki = OutoWiki(config)
    wiki.record("Important information")
    results = wiki.search("information")
"""

from .core.config import WikiConfig, ProviderConfig, WikiSettings
from .core.store import WikiStore
from .core.facade import OutoWiki
from .core.exceptions import (
    OutoWikiError,
    ProviderError,
    WikiStoreError,
    ValidationError,
    ConfigError
)
from .models.content import RawContent, WikiDocument, DocumentMetadata
from .models.search import SearchQuery, SearchResult
from .models.plans import PlanType, Plan, CreatePlan, ModifyPlan, MergePlan, SplitPlan, DeletePlan
from .models.analysis import AnalysisResult, IntentAnalysis
from .modules.recorder import Recorder, RecordResult
from .modules.searcher import Searcher
from .modules.agent import InternalAgent
from .providers.base import LLMProvider

__version__ = "0.6.3"


def __getattr__(name: str) -> type:
    if name == "OpenAIProvider":
        try:
            from .providers.openai import OpenAIProvider
            return OpenAIProvider
        except ImportError:
            raise ImportError(
                "OpenAIProvider requires the 'openai' package. "
                "Install it with: pip install openai"
            )
    elif name == "AnthropicProvider":
        try:
            from .providers.anthropic import AnthropicProvider
            return AnthropicProvider
        except ImportError:
            raise ImportError(
                "AnthropicProvider requires the 'anthropic' package. "
                "Install it with: pip install anthropic"
            )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'OutoWiki',
    'WikiConfig',
    'ProviderConfig',
    'WikiSettings',
    'WikiStore',
    'OutoWikiError',
    'ProviderError',
    'WikiStoreError',
    'ValidationError',
    'ConfigError',
    'RawContent',
    'WikiDocument',
    'DocumentMetadata',
    'SearchQuery',
    'SearchResult',
    'PlanType',
    'Plan',
    'CreatePlan',
    'ModifyPlan',
    'MergePlan',
    'SplitPlan',
    'DeletePlan',
    'AnalysisResult',
    'IntentAnalysis',
    'Recorder',
    'RecordResult',
    'Searcher',
    'InternalAgent',
    'LLMProvider',
    'OpenAIProvider',
    'AnthropicProvider',
]
