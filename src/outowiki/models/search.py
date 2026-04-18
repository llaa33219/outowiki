"""Search models for OutoWiki - query and result structures.

Defines the input and output types for the search pipeline,
including query parameters, result formats, and intent analysis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel

from outowiki.models.analysis import IntentAnalysis
from outowiki.models.content import WikiDocument


class SearchQuery(BaseModel):
    """A search query against the wiki knowledge base.

    Supports natural language queries with optional filters for
    category, time range, and result count/format control.
    """

    query: str
    context: Optional[str] = None
    category_filter: Optional[str] = None
    time_range: Optional[Tuple[datetime, datetime]] = None
    max_results: int = 10
    return_mode: Literal["path", "summary", "full"] = "path"


class SearchResult(BaseModel):
    """Result of a wiki search operation.

    Always contains document paths. Summaries and full documents
    are included based on the query's return_mode.
    """

    paths: List[str]
    summaries: Optional[Dict[str, str]] = None
    documents: Optional[Dict[str, WikiDocument]] = None
    query_analysis: Optional[IntentAnalysis] = None
