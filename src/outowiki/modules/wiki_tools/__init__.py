"""Wiki I/O tools for agent loop."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import PurePosixPath

from pydantic import BaseModel, Field

from ...core.store import WikiStore
from ...core.exceptions import WikiStoreError
from ...models.content import WikiDocument
from ...utils.validation import validate_document, title_to_filename, auto_correct_filename
from ..tools import ToolDefinition

logger = logging.getLogger(__name__)


class ReadDocumentInput(BaseModel):
    path: str = Field(description="Document path (without .md extension)")


class ReadDocumentOutput(BaseModel):
    title: str
    content: str
    tags: list[str] = []
    category: str | None = None
    related: list[str] = []


class WriteDocumentInput(BaseModel):
    path: str = Field(description="Document path (without .md extension)")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content in markdown")
    tags: list[str] = Field(default_factory=list, description="Document tags")
    category: str | None = Field(default=None, description="Document category")
    related: list[str] = Field(default_factory=list, description="Related document paths")


class WriteDocumentOutput(BaseModel):
    path: str
    success: bool = True


class DeleteDocumentInput(BaseModel):
    path: str = Field(description="Document path to delete")
    remove_backlinks: bool = Field(default=True, description="Whether to remove backlinks")


class DeleteDocumentOutput(BaseModel):
    path: str
    success: bool = True


class ListFolderInput(BaseModel):
    path: str = Field(default="", description="Folder path (empty for root)")


class ListFolderOutput(BaseModel):
    files: list[str] = []
    folders: list[str] = []


class ListCategoriesInput(BaseModel):
    max_depth: int = Field(default=4, description="Maximum depth to explore")


class ListCategoriesOutput(BaseModel):
    categories: list[str] = []


class SearchTitlesInput(BaseModel):
    query: str = Field(description="Search query to match against document titles")
    max_results: int = Field(default=20, description="Maximum number of results to return")


class SearchTitlesOutput(BaseModel):
    results: list[dict[str, str]] = Field(default_factory=list, description="List of matching documents with path, title, category")


def create_wiki_tools(wiki: WikiStore) -> list[ToolDefinition]:
    """Create wiki I/O tools bound to a WikiStore instance."""
    
    def read_document(input: ReadDocumentInput) -> ReadDocumentOutput:
        doc = wiki.read_document(input.path)
        return ReadDocumentOutput(
            title=doc.title,
            content=doc.content,
            tags=doc.tags,
            category=doc.category,
            related=doc.related,
        )
    
    def write_document(input: WriteDocumentInput) -> WriteDocumentOutput:
        is_valid, errors = validate_document(input.title, input.path, input.tags)
        if not is_valid:
            for error in errors:
                logger.warning(f"Validation warning: {error}")
            if any("must be in English" in e for e in errors):
                raise WikiStoreError(f"Document validation failed: {'; '.join(errors)}")

        path = input.path
        path = auto_correct_filename(input.title, path)
        logger.debug(f"Auto-corrected path: {path}")

        doc = WikiDocument(
            path=path,
            title=input.title,
            content=input.content,
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=input.tags,
            category=input.category,
            related=input.related,
        )
        wiki.write_document(path, doc)
        return WriteDocumentOutput(path=path)
    
    def delete_document(input: DeleteDocumentInput) -> DeleteDocumentOutput:
        wiki.delete_document(input.path, remove_backlinks=input.remove_backlinks)
        return DeleteDocumentOutput(path=input.path)
    
    def list_folder(input: ListFolderInput) -> ListFolderOutput:
        content = wiki.list_folder(input.path)
        return ListFolderOutput(
            files=content.get("files", []),
            folders=content.get("folders", []),
        )
    
    def list_categories(input: ListCategoriesInput) -> ListCategoriesOutput:
        categories: list[str] = []
        
        def collect(path: str, depth: int) -> None:
            if depth >= input.max_depth:
                return
            try:
                content = wiki.list_folder(path)
                for folder in content.get("folders", []):
                    folder_path = f"{path}/{folder}" if path else folder
                    categories.append(folder_path)
                    collect(folder_path, depth + 1)
            except Exception:
                pass
        
        collect("", 0)
        return ListCategoriesOutput(categories=categories)
    
    def search_titles(input: SearchTitlesInput) -> SearchTitlesOutput:
        results = wiki.search_titles(input.query, input.max_results)
        return SearchTitlesOutput(results=results)
    
    return [
        ToolDefinition(
            name="read_document",
            description="Read a wiki document by path",
            input_model=ReadDocumentInput,
            handler=read_document,
        ),
        ToolDefinition(
            name="write_document",
            description="Create or update a wiki document",
            input_model=WriteDocumentInput,
            handler=write_document,
        ),
        ToolDefinition(
            name="delete_document",
            description="Delete a wiki document",
            input_model=DeleteDocumentInput,
            handler=delete_document,
        ),
        ToolDefinition(
            name="list_folder",
            description="List files and folders in a wiki directory",
            input_model=ListFolderInput,
            handler=list_folder,
        ),
        ToolDefinition(
            name="list_categories",
            description="List all categories in the wiki",
            input_model=ListCategoriesInput,
            handler=list_categories,
        ),
        ToolDefinition(
            name="search_titles",
            description="Search document titles by keyword. FAST way to find documents by title.",
            input_model=SearchTitlesInput,
            handler=search_titles,
        ),
    ]
