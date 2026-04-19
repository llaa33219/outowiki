# API Reference: Exceptions

## OutoWikiError

Base exception for all OutoWiki errors.

```python
from outowiki.exceptions import OutoWikiError

try:
    wiki.record("content")
except OutoWikiError as e:
    print(f"Wiki error: {e}")
```

All other exceptions inherit from this base class.

## ConfigurationError

Raised for invalid configuration.

```python
from outowiki.exceptions import ConfigurationError

# Inherits from OutoWikiError
raise ConfigurationError("Invalid API key format")
```

## DocumentNotFoundError

Raised when a document cannot be found.

```python
from outowiki.exceptions import DocumentNotFoundError

try:
    doc = wiki.get_document("nonexistent.md")
except DocumentNotFoundError:
    print("Document not found")
```

## ProviderError

Raised when the LLM provider returns an error.

```python
from outowiki.exceptions import ProviderError

try:
    wiki.record("content")
except ProviderError as e:
    print(f"Provider error: {e}")
```

## PlanError

Raised when plan execution fails.

```python
from outowiki.exceptions import PlanError

# Inherited from OutoWikiError
raise PlanError("Cannot merge: documents incompatible")
```

## ValidationError

Raised for invalid input data.

```python
from outowiki.exceptions import ValidationError

# Inherited from OutoWikiError
raise ValidationError("SearchQuery.time_range requires (start, end) tuple")
```
