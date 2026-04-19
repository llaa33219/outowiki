"""Configuration management for OutoWiki."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from .exceptions import ConfigError


class ProviderConfig(BaseModel):
    """LLM provider configuration.

    Attributes:
        provider: LLM provider type (openai/anthropic)
        base_url: API endpoint URL
        api_key: API key for authentication
        model: Model identifier
        max_output_tokens: Maximum output tokens for LLM response.
            OpenAI uses 'max_tokens' parameter.
            Anthropic uses 'max_tokens' parameter.
    """

    provider: Literal["openai", "anthropic"] = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4"
    max_output_tokens: int = Field(default=4000, ge=100, le=100000)


class WikiSettings(BaseModel):
    """Wiki operational settings."""

    token_threshold: int = Field(default=4000, description="Document split threshold")
    stub_threshold: int = Field(default=300, description="Stub merge threshold")
    auto_backlinks: bool = True
    auto_index: bool = True
    default_category: str = Field(default="unassigned", description="Default category when classification fails")
    init_default_folders: bool = Field(default=True, description="Create default category folders on initialization")


class WikiConfig(BaseModel):
    """OutoWiki configuration.

    Can be loaded from YAML/JSON or constructed directly.

    Example:
        config = WikiConfig(
            provider="openai",
            api_key="sk-...",
            model="gpt-4",
            max_output_tokens=4000,
            wiki_path="./my_wiki",
            debug=True
        )
    """

    # Provider settings
    provider: Literal["openai", "anthropic"] = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4"
    max_output_tokens: int = Field(default=4000, ge=100, le=100000)

    # Wiki settings
    wiki_path: str = "./wiki"
    settings: WikiSettings = Field(default_factory=WikiSettings)
    
    # Debug settings
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator('wiki_path')
    @classmethod
    def validate_wiki_path(cls, v: str) -> str:
        """Ensure wiki_path is a valid directory path."""
        path = Path(v)
        if path.exists() and not path.is_dir():
            raise ConfigError(f"wiki_path exists but is not a directory: {v}")
        return str(path.resolve())

    @classmethod
    def from_yaml(cls, path: str | Path) -> WikiConfig:
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            WikiConfig instance

        Raises:
            ConfigError: If file doesn't exist or is invalid
        """
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return cls(**data)
        except Exception as e:
            raise ConfigError(f"Failed to load config: {e}") from e

    def to_yaml(self, path: str | Path) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save configuration
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)

    def get_provider_config(self) -> ProviderConfig:
        return ProviderConfig(
            provider=self.provider,
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            max_output_tokens=self.max_output_tokens
        )
