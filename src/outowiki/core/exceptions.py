"""OutoWiki exception hierarchy."""


class OutoWikiError(Exception):
    """Base exception for OutoWiki."""

    pass


class ProviderError(OutoWikiError):
    """LLM provider error."""

    pass


class WikiStoreError(OutoWikiError):
    """Wiki storage error."""

    pass


class ValidationError(OutoWikiError):
    """Data validation error."""

    pass


class ConfigError(OutoWikiError):
    """Configuration error."""

    pass
