"""Main facade providing the high-level OutoWiki API."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from ..models.content import WikiDocument
from ..models.search import SearchQuery, SearchResult
from ..providers.base import LLMProvider
from .config import WikiConfig
from .store import WikiStore
from .exceptions import ConfigError
from ..modules.agent import InternalAgent
from ..modules.recorder import Recorder, RecordResult
from ..modules.searcher import Searcher


class OutoWiki:
    """Main interface for OutoWiki library.

    Provides simple methods to record information and search the wiki.
    All internal complexity (providers, agents, pipelines) is hidden.

    Example:
        from outowiki import OutoWiki, WikiConfig

        config = WikiConfig(
            provider="openai",
            api_key="sk-...",
            model="gpt-4",
            wiki_path="./my_wiki",
            debug=True
        )

        wiki = OutoWiki(config)

        # Record information
        result = wiki.record("User prefers Python for web development")

        # Search information
        results = wiki.search("user programming preferences")
        print(results.paths)
    """

    def __init__(self, config: Optional[WikiConfig] = None):
        """Initialize OutoWiki.

        Args:
            config: Wiki configuration. If None, uses defaults.

        Raises:
            ConfigError: If configuration is invalid
        """
        self.config = config or WikiConfig()
        self._setup_logging()
        self._initialize()

    def _setup_logging(self) -> None:
        """Configure logging based on debug settings."""
        self.logger = logging.getLogger("outowiki")
        self.logger.handlers.clear()
        
        if self.config.debug:
            level = logging.DEBUG
        else:
            level = getattr(logging, self.config.log_level, logging.INFO)
        
        self.logger.setLevel(level)
        
        handler = logging.StreamHandler()
        handler.setLevel(level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False

    def _mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive information like API keys in log output."""
        patterns = [
            (r'(sk-[a-zA-Z0-9]{20,})', 'sk-***MASKED***'),
            (r'(sk-ant-[a-zA-Z0-9]{20,})', 'sk-ant-***MASKED***'),
            (r'(api[_-]?key["\s:=]+["\']?)([a-zA-Z0-9]{20,})', r'\1***MASKED***'),
        ]
        
        masked = text
        for pattern, replacement in patterns:
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
        
        return masked

    def _initialize(self) -> None:
        """Initialize internal components."""
        self._provider = self._create_provider()
        self._store = WikiStore(self.config.wiki_path)
        self._agent = InternalAgent(self._provider, self.logger)
        self._recorder = Recorder(self._store, self._agent, self.logger)
        self._searcher = Searcher(self._store, self._agent, self.logger)
        
        if self.config.debug:
            self.logger.debug("OutoWiki initialized with debug mode enabled")
            self.logger.debug(f"Wiki path: {self.config.wiki_path}")
            self.logger.debug(f"Provider: {self.config.provider}")
            masked_key = self._mask_sensitive_data(self.config.api_key)
            self.logger.debug(f"API key: {masked_key}")

    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on config.

        Returns:
            LLMProvider instance

        Raises:
            ConfigError: If provider type is unknown
        """
        provider_config = self.config.get_provider_config()

        if self.config.provider == "openai":
            from ..providers.openai import OpenAIProvider
            return OpenAIProvider(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=provider_config.model,
                max_tokens=provider_config.max_output_tokens
            )
        elif self.config.provider == "anthropic":
            from ..providers.anthropic import AnthropicProvider
            return AnthropicProvider(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=provider_config.model,
                max_tokens=provider_config.max_output_tokens
            )
        else:
            raise ConfigError(f"Unknown provider: {self.config.provider}")

    def configure(
        self,
        provider: Optional[Literal["openai", "anthropic"]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        wiki_path: Optional[str] = None
    ) -> None:
        """Update configuration.

        Args:
            provider: Provider type (openai/anthropic)
            api_key: API key
            base_url: Base URL for API
            model: Model name
            max_output_tokens: Maximum output tokens for LLM response
            wiki_path: Wiki directory path
        """
        if provider is not None:
            self.config.provider = provider
        if api_key is not None:
            self.config.api_key = api_key
        if base_url is not None:
            self.config.base_url = base_url
        if model is not None:
            self.config.model = model
        if max_output_tokens is not None:
            self.config.max_output_tokens = max_output_tokens
        if wiki_path is not None:
            self.config.wiki_path = wiki_path

        self._initialize()

    def record(
        self,
        content: Union[str, Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> RecordResult:
        """Record information to the wiki.

        Args:
            content: Raw content (string or structured dict)
            metadata: Optional metadata (type, context, etc.)

        Returns:
            RecordResult with actions taken

        Example:
            # Simple string
            result = wiki.record("User prefers Python")

            # Structured content
            result = wiki.record({
                "type": "conversation",
                "content": "User: I like Python\\nAgent: Great!",
                "context": "programming"
            })
        """
        return self._recorder.record(content, metadata)

    def search(
        self,
        query: Union[str, SearchQuery],
        category_filter: Optional[str] = None,
        max_results: int = 10,
        return_mode: Literal["path", "summary", "full"] = "path"
    ) -> SearchResult:
        """Search the wiki for information.

        Args:
            query: Search query (string or SearchQuery object)
            category_filter: Optional category to limit search
            max_results: Maximum number of results
            return_mode: Return format (path/summary/full)

        Returns:
            SearchResult with document paths and optional content

        Example:
            # Simple search
            results = wiki.search("user preferences")

            # With filters
            results = wiki.search(
                "python",
                category_filter="knowledge/programming",
                return_mode="summary"
            )
        """
        if isinstance(query, str):
            search_query = SearchQuery(
                query=query,
                category_filter=category_filter,
                max_results=max_results,
                return_mode=return_mode
            )
        else:
            search_query = query

        return self._searcher.search(search_query)

    def get_document(self, path: str) -> WikiDocument:
        """Get a document by path.

        Args:
            path: Document path (with or without .md extension)

        Returns:
            WikiDocument instance

        Raises:
            WikiStoreError: If document doesn't exist
        """
        return self._store.read_document(path)

    def update_document(self, path: str, content: str) -> None:
        """Update a document's content.

        Args:
            path: Document path
            content: New markdown content

        Raises:
            WikiStoreError: If document doesn't exist
        """
        doc = self._store.read_document(path)
        doc.content = content
        self._store.write_document(path, doc)

    def delete_document(
        self,
        path: str,
        remove_backlinks: bool = True
    ) -> None:
        """Delete a document.

        Args:
            path: Document path
            remove_backlinks: Whether to update backlinks

        Raises:
            WikiStoreError: If document doesn't exist
        """
        self._store.delete_document(path, remove_backlinks)

    def list_categories(self, folder: str = "") -> List[str]:
        """List categories (folders) in the wiki.

        Args:
            folder: Parent folder (empty for root)

        Returns:
            List of category names
        """
        content = self._store.list_folder(folder)
        return content['folders']

    def list_documents(self, folder: str = "") -> List[str]:
        """List documents in a folder.

        Args:
            folder: Folder path (empty for root)

        Returns:
            List of document names (without .md)
        """
        content = self._store.list_folder(folder)
        return content['files']

    @property
    def wiki_path(self) -> Path:
        """Get the wiki root path."""
        return self._store.root

    @property
    def provider(self) -> LLMProvider:
        """Get the current LLM provider."""
        return self._provider
