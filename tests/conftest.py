from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from outowiki.models.content import WikiDocument


@pytest.fixture
def tmp_wiki(tmp_path: Path) -> Path:
    """Create a temporary wiki directory structure for testing."""
    wiki_dir = tmp_path / "test_wiki"
    wiki_dir.mkdir()
    return wiki_dir


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider for testing."""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value="mocked response")
    provider.analyze = AsyncMock(return_value={"analysis": "mocked"})
    return provider


@pytest.fixture
def sample_document() -> WikiDocument:
    """Create a sample WikiDocument for testing."""
    return WikiDocument(
        title="Test Document",
        content="# Test Document\n\nThis is test content.\n",
        tags=["test", "sample"],
    )
