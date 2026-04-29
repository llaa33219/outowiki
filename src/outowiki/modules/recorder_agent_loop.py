"""Information recording pipeline for OutoWiki (AgentLoop version)."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..core.store import WikiStore
from ..core.exceptions import WikiStoreError
from ..models.content import WikiDocument
from ..utils.markdown import extract_sections, parse_frontmatter
from ..utils.validation import validate_document, title_to_filename, auto_correct_filename
from ..providers.base import LLMProvider
from .agent_loop import AgentLoop
from .tools import ToolDefinition
from .wiki_tools import create_wiki_tools
from .reasoning_tools import create_reasoning_tools


SYSTEM_PROMPT = """You are a wiki recording assistant. Your job is to analyze content and record it to the wiki.

You have access to these tools:
- search_titles: Search document titles by keyword (FASTEST way to find existing documents)
- list_categories: List all categories in the wiki
- list_folder: List files and folders in a directory
- read_document: Read a wiki document by path
- write_document: Create or update a wiki document
- delete_document: Delete a wiki document
- generate_document: Generate document content from raw content
- split_topics: Split content into multiple topics using LLM analysis
- find_existing_document: Find existing documents via wikilinks and category matching
- classify_topic: Determine which category content belongs to
- execute_create_plan: Create a new document with validation and version tracking
- execute_modify_plan: Modify existing document (append, prepend, replace_section) with version tracking
- execute_merge_plan: Merge multiple documents with version tracking
- execute_split_plan: Split document into sub-documents with version tracking
- execute_delete_plan: Delete a document with version tracking

CRITICAL WORKFLOW - Follow this EXACTLY:
1. FIRST: Use split_topics to check if content contains multiple unrelated topics
   - If multiple topics detected, process EACH topic separately (go to step 2 for each)
   - If single topic, continue with the full content

2. For each topic:
   a. Use find_existing_document to search for related existing documents
   b. If existing document found:
      - Read it with read_document to verify and check current content
      - Use execute_modify_plan to update it (append/prepend/replace_section)
   c. If no existing document:
      - Use classify_topic to determine the best category
      - Use execute_create_plan to create a new document

3. For complex operations (MERGE, SPLIT, DELETE):
   - Use the appropriate execute_*_plan tool
   - These handle version tracking automatically

CRITICAL RULES - NEVER VIOLATE:
1. NEVER write content to category README.md files
   - README.md files are for category descriptions ONLY
   - Create SEPARATE topic-specific documents instead

2. NEVER put multiple topics in one document
   - Each topic gets its OWN document

3. ALWAYS create specific, focused documents
   - Document should be about ONE specific topic
   - Use descriptive filenames

4. TITLE and FILENAME must be CONSISTENT
   - File name (without .md) should be derived from the title
   - Rules: lowercase, spaces→underscores, remove special chars

5. Title and tags MUST be in English ONLY
   - Content can be in any language, but title and tags must be English

6. ALWAYS use execute_*_plan tools for document operations
   - They handle validation, frontmatter stripping, and version tracking
   - Do NOT use raw write_document for recording operations

When you have finished recording, respond with a JSON object:
{"success": true, "actions": ["Created: path1", "Modified: path2"], "documents": ["path1", "path2"]}

Always use the tools to explore the wiki. Do not guess - verify paths and content first."""


class RecordResult:
    """Result of a recording operation."""

    def __init__(
        self,
        success: bool,
        actions_taken: List[str],
        documents_affected: List[str],
        error: Optional[str] = None
    ):
        self.success = success
        self.actions_taken = actions_taken
        self.documents_affected = documents_affected
        self.error = error

    def __repr__(self) -> str:
        if self.success:
            return f"RecordResult(success=True, actions={self.actions_taken})"
        return f"RecordResult(success=False, error={self.error})"


# ── Tool input/output models ──────────────────────────────────────────


class TopicSplitResult(BaseModel):
    topics: List[str] = []


class CategoryResult(BaseModel):
    category: str = ""


class SplitTopicsInput(BaseModel):
    content: str = Field(description="Content to analyze and split into separate topics")


class SplitTopicsOutput(BaseModel):
    topics: List[str] = Field(default_factory=list, description="List of separated topic contents")
    is_single_topic: bool = Field(default=True, description="Whether content is a single topic")


class FindExistingDocumentInput(BaseModel):
    content: str = Field(description="Content to search for related existing documents")
    wikilinks: List[str] = Field(default_factory=list, description="Extracted wikilinks from content")


class FindExistingDocumentOutput(BaseModel):
    found_paths: List[str] = Field(default_factory=list, description="Paths of found existing documents")
    existing_contents: Dict[str, str] = Field(default_factory=dict, description="Content preview of found documents")


class ClassifyTopicInput(BaseModel):
    content: str = Field(description="Content to classify into a category")


class ClassifyTopicOutput(BaseModel):
    category: str = Field(description="Category path for the content")
    is_new_category: bool = Field(default=False, description="Whether a new category was created")


class ExecuteCreatePlanInput(BaseModel):
    target_path: str = Field(description="Target document path (without .md extension)")
    title: str = Field(description="Document title (English only)")
    content: str = Field(description="Document content in markdown")
    category: Optional[str] = Field(default=None, description="Document category")
    tags: List[str] = Field(default_factory=list, description="Document tags (English only)")
    related: List[str] = Field(default_factory=list, description="Related document paths")


class ExecuteCreatePlanOutput(BaseModel):
    path: str
    success: bool = True
    action: str = "Created"


class ExecuteModifyPlanInput(BaseModel):
    target_path: str = Field(description="Path of document to modify")
    modifications: List[Dict[str, Any]] = Field(
        description="List of modifications. Each has: operation (append/prepend/replace_section/append_section_after), content, and optional section"
    )


class ExecuteModifyPlanOutput(BaseModel):
    path: str
    success: bool = True
    action: str = "Modified"


class ExecuteMergePlanInput(BaseModel):
    target_path: str = Field(description="Path for the merged document")
    source_paths: List[str] = Field(description="Paths of documents to merge")
    merged_content: str = Field(description="Content for the merged document")
    redirect_sources: bool = Field(default=True, description="Delete source documents after merge")


class ExecuteMergePlanOutput(BaseModel):
    path: str
    success: bool = True
    action: str = "Merged"
    sources_deleted: bool = False


class ExecuteSplitPlanInput(BaseModel):
    target_path: str = Field(description="Path of document to split")
    sections_to_split: List[Dict[str, str]] = Field(
        description="Sections to extract. Each has: new_path, content"
    )
    summary_for_main: str = Field(description="Summary content to replace extracted sections in main doc")


class ExecuteSplitPlanOutput(BaseModel):
    path: str
    success: bool = True
    action: str = "Split"
    new_paths: List[str] = Field(default_factory=list)


class ExecuteDeletePlanInput(BaseModel):
    target_path: str = Field(description="Path of document to delete")
    remove_backlinks: bool = Field(default=True, description="Whether to remove backlinks")


class ExecuteDeletePlanOutput(BaseModel):
    path: str
    success: bool = True
    action: str = "Deleted"


# ── Tool creation ─────────────────────────────────────────────────────


def create_recorder_tools(
    wiki: WikiStore,
    provider: LLMProvider,
    logger: logging.Logger | None = None,
) -> list[ToolDefinition]:
    """Create recorder-specific tools bound to wiki store and provider."""

    _logger = logger or logging.getLogger(__name__)

    # ── Helper: category tree exploration ────────────────────────────

    def _explore_category_tree(category: str = "", depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
        if depth > max_depth:
            return {'category': category, 'files': [], 'subcategories': [], 'truncated': True}
        try:
            folder_content = wiki.list_folder(category)
            result: Dict[str, Any] = {
                'category': category,
                'files': folder_content.get('files', []),
                'subcategories': [],
                'truncated': False,
            }
            for subfolder in folder_content.get('folders', []):
                subcategory_path = f"{category}/{subfolder}" if category else subfolder
                subcategory_result = _explore_category_tree(subcategory_path, depth + 1, max_depth)
                result['subcategories'].append(subcategory_result)
            return result
        except WikiStoreError:
            return {'category': category, 'files': [], 'subcategories': [], 'truncated': False}

    def _create_category_if_needed(category: str) -> bool:
        if not category:
            return False
        try:
            wiki.list_folder(category)
            return False
        except WikiStoreError:
            pass
        parts = category.split('/')
        current_path = ""
        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            try:
                wiki.list_folder(current_path)
            except WikiStoreError:
                _logger.debug(f"Creating category folder: {current_path}")
                wiki.create_folder(current_path)
        doc_path = f"{category}/README.md"
        if not wiki.document_exists(doc_path):
            category_name = category.split('/')[-1]
            doc = WikiDocument(
                path=doc_path,
                title=category_name,
                content=f"# {category_name}\n\nThis category contains documents related to {category_name}.",
                frontmatter={},
                created=datetime.now(),
                modified=datetime.now(),
                tags=[],
                category=category,
                related=[],
            )
            wiki.write_document(doc_path, doc)
            _logger.debug(f"Created category README: {doc_path}")
        return True

    def _find_document_in_category(category: str, content: str) -> Optional[str]:
        try:
            folder_content = wiki.list_folder(category)
            if folder_content['files']:
                _logger.debug(f"Found documents in category {category}: {folder_content['files']}")
                return f"{category}/{folder_content['files'][0]}"
        except WikiStoreError:
            pass

        # Check subcategories recursively (up to 3 levels deep)
        def _check_subcategories(cat: str, depth: int) -> Optional[str]:
            if depth > 3:
                return None
            try:
                folder_content = wiki.list_folder(cat)
                for subfolder in folder_content.get('folders', []):
                    subcat = f"{cat}/{subfolder}" if cat else subfolder
                    try:
                        sub_content = wiki.list_folder(subcat)
                        if sub_content['files']:
                            _logger.debug(f"Found documents in subcategory {subcat}: {sub_content['files']}")
                            return f"{subcat}/{sub_content['files'][0]}"
                    except WikiStoreError:
                        continue
                    # Recurse deeper
                    result = _check_subcategories(subcat, depth + 1)
                    if result:
                        return result
            except WikiStoreError:
                pass
            return None

        return _check_subcategories(category, 0)

    # ── Helper: section operations ───────────────────────────────────

    def _append_section_after(content: str, target_section: str, new_content: str) -> str:
        lines = content.split('\n')
        new_lines: List[str] = []
        inserted = False
        target_level: Optional[int] = None

        for i, line in enumerate(lines):
            new_lines.append(line)

            if line.startswith('#'):
                level = 0
                for ch in line:
                    if ch == '#':
                        level += 1
                    else:
                        break
                title_text = line[level:].strip()

                if title_text == target_section and not inserted:
                    target_level = level
                    new_lines.append('')
                    new_lines.append(new_content)
                    inserted = True
                elif inserted and target_level is not None and level <= target_level:
                    new_lines.pop()
                    new_lines.append('')
                    new_lines.append(new_content)
                    new_lines.append(line)
                    inserted = False

        if inserted:
            new_lines.append('')

        return '\n'.join(new_lines)

    # ── Tool: split_topics ───────────────────────────────────────────

    def split_topics(input: SplitTopicsInput) -> SplitTopicsOutput:
        prompt = f"""Analyze this text and identify ALL distinct topics/subjects that are mixed together.

Text:
{input.content}

IMPORTANT: Even if the text flows as one narrative, it may contain MULTIPLE unrelated subjects.

Examples of mixed content:
1. "Linux Mint was developed by Clement Lefebvre. Aluminum has atomic number 13. OpenBSD was created by Theo de Raadt."
   -> Topics: ["Linux Mint was developed by Clement Lefebvre.", "Aluminum has atomic number 13.", "OpenBSD was created by Theo de Raadt."]

2. "React is a library developed by Facebook. The speed of light is 300,000 km/s. Python was created by Guido van Rossum."
   -> Topics: ["React is a library developed by Facebook.", "The speed of light is 300,000 km/s.", "Python was created by Guido van Rossum."]

Your task:
1. Identify EVERY distinct subject/topic mentioned
2. Extract the content related to each topic separately
3. Topics can be completely unrelated to each other

Return a JSON object with a "topics" array containing the separated content blocks.
Example: {{"topics": ["Content about topic 1...", "Content about topic 2...", "Content about topic 3..."]}}

Be thorough - extract ALL topics, even if there are 3, 4, or more."""

        try:
            result = provider.complete_with_schema(prompt, TopicSplitResult)
            if result.topics:
                topics = [t.strip() for t in result.topics if t.strip() and len(t.strip()) > 20]
                if len(topics) > 1:
                    _logger.debug(f"LLM split into {len(topics)} topics")
                    return SplitTopicsOutput(topics=topics, is_single_topic=False)
        except Exception as e:
            _logger.debug(f"LLM topic splitting failed: {e}")

        return SplitTopicsOutput(topics=[input.content], is_single_topic=True)

    # ── Tool: find_existing_document ──────────────────────────────────

    def find_existing_document(input: FindExistingDocumentInput) -> FindExistingDocumentOutput:
        found_paths: List[str] = []
        existing_contents: Dict[str, str] = {}

        # Check wikilinks first
        for link in input.wikilinks:
            normalized = link.replace(' ', '_').lower()
            if wiki.document_exists(normalized):
                found_paths.append(normalized)
                _logger.debug(f"Found via wikilink: {normalized}")
            elif wiki.document_exists(link):
                found_paths.append(link)
                _logger.debug(f"Found via wikilink: {link}")

        # If not found via wikilinks, try category matching
        if not found_paths:
            topic_category = _classify_topic_internal(input.content)
            if topic_category:
                doc_path = _find_document_in_category(topic_category, input.content)
                if doc_path:
                    found_paths.append(doc_path)

        # Read content previews for found documents
        for path in found_paths:
            try:
                doc = wiki.read_document(path)
                existing_contents[path] = doc.content[:500]
            except WikiStoreError:
                pass

        return FindExistingDocumentOutput(found_paths=found_paths, existing_contents=existing_contents)

    def _classify_topic_internal(content: str) -> Optional[str]:
        """Internal classify topic used by find_existing_document."""
        category_tree = _explore_category_tree()

        def format_tree(tree: Dict[str, Any], indent: int = 0) -> List[str]:
            lines: List[str] = []
            if tree['category']:
                lines.append("  " * indent + f"- {tree['category']}/ ({len(tree['files'])} files)")
            for sub in tree['subcategories']:
                lines.extend(format_tree(sub, indent + 1))
            return lines

        tree_lines = format_tree(category_tree)
        tree_str = "\n".join(tree_lines) if tree_lines else "(Empty category tree - create new categories)"

        prompt = f"""Analyze this content and determine which category it belongs to.

Content: {content[:500]}

Available category tree:
{tree_str}

Determine the SINGLE most specific category this content belongs to.
If no existing category fits well, suggest a NEW category path (e.g., "programming/python/web").

Return the category path (e.g., "programming/python/web")."""

        try:
            result = provider.complete_with_schema(prompt, CategoryResult)
            if result.category:
                _create_category_if_needed(result.category)
                return result.category
        except Exception as e:
            _logger.debug(f"Topic classification failed: {e}")

        return None

    # ── Tool: classify_topic ─────────────────────────────────────────

    def classify_topic(input: ClassifyTopicInput) -> ClassifyTopicOutput:
        category = _classify_topic_internal(input.content)
        if category:
            return ClassifyTopicOutput(category=category, is_new_category=False)

        # Default: suggest a new category based on content
        return ClassifyTopicOutput(category="", is_new_category=False)

    # ── Tool: execute_create_plan ────────────────────────────────────

    def execute_create_plan(input: ExecuteCreatePlanInput) -> ExecuteCreatePlanOutput:
        category = input.category
        target_path = input.target_path

        # Validate document
        is_valid, errors = validate_document(input.title, target_path, input.tags)
        if not is_valid:
            for error in errors:
                _logger.warning(f"Validation warning: {error}")
            if any("must be in English" in e for e in errors):
                raise WikiStoreError(f"Document validation failed: {'; '.join(errors)}")

        # Auto-correct filename to match title
        target_path = auto_correct_filename(input.title, target_path)
        _logger.debug(f"Auto-corrected path: {target_path}")

        if not category and '/' in target_path:
            category = '/'.join(target_path.split('/')[:-1])
            _logger.debug(f"Extracted category from path: {category}")
        elif not category:
            category = _classify_topic_internal(input.content)
            if category:
                target_path = f"{category}/{target_path}"
                _logger.debug(f"Assigned category from content: {category}")
            else:
                category = "general"
                target_path = f"{category}/{target_path}"
                _logger.debug(f"Using default category: {category}")

        if category and '/' not in target_path:
            target_path = f"{category}/{target_path}"
            _logger.debug(f"Using category as path prefix: {target_path}")

        # Strip frontmatter from content
        _, body_content = parse_frontmatter(input.content)

        doc = WikiDocument(
            path=target_path,
            title=input.title,
            content=body_content,
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=input.tags,
            category=category,
            related=input.related,
        )

        wiki.write_document(target_path, doc)
        wiki.save_version(target_path, "create")

        return ExecuteCreatePlanOutput(path=target_path, action="Created")

    # ── Tool: execute_modify_plan ────────────────────────────────────

    def execute_modify_plan(input: ExecuteModifyPlanInput) -> ExecuteModifyPlanOutput:
        if not wiki.document_exists(input.target_path):
            raise WikiStoreError(
                f"Cannot modify document that does not exist: {input.target_path}. "
                f"Please use execute_create_plan instead, or verify the document path."
            )

        wiki.save_version(input.target_path, "modify")
        doc = wiki.read_document(input.target_path)

        for mod in input.modifications:
            section = mod.get('section')
            operation = mod.get('operation', 'append')
            _, mod_body = parse_frontmatter(mod.get('content', ''))

            if operation == 'append':
                doc.content += f"\n\n{mod_body}"
            elif operation == 'prepend':
                doc.content = f"{mod_body}\n\n{doc.content}"
            elif operation == 'append_section_after':
                if section:
                    doc.content = _append_section_after(doc.content, section, mod_body)
                else:
                    doc.content += f"\n\n{mod_body}"
            elif operation == 'replace_section':
                sections = extract_sections(doc.content)
                target_level = None
                for sec in sections:
                    if sec['title'] == section:
                        target_level = int(sec['level'])
                        break

                if target_level is not None:
                    lines = doc.content.split('\n')
                    new_lines: List[str] = []
                    in_target = False

                    for line in lines:
                        if line.startswith('#'):
                            level = 0
                            for ch in line:
                                if ch == '#':
                                    level += 1
                                else:
                                    break
                            title_text = line[level:].strip()

                            if title_text == section and level == target_level:
                                in_target = True
                                new_lines.append(line)
                                new_lines.append(mod_body)
                                continue
                            elif in_target:
                                in_target = False

                        if not in_target:
                            new_lines.append(line)

                    doc.content = '\n'.join(new_lines)

        wiki.write_document(input.target_path, doc)
        return ExecuteModifyPlanOutput(path=input.target_path, action="Modified")

    # ── Tool: execute_merge_plan ─────────────────────────────────────

    def execute_merge_plan(input: ExecuteMergePlanInput) -> ExecuteMergePlanOutput:
        for source_path in input.source_paths:
            if wiki.document_exists(source_path):
                wiki.save_version(source_path, "merge")

        _, merged_body = parse_frontmatter(input.merged_content)

        doc = WikiDocument(
            path=input.target_path,
            title=input.target_path.split('/')[-1].replace('_', ' ').title(),
            content=merged_body,
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category='/'.join(input.target_path.split('/')[:-1]) or "general",
            related=input.source_paths,
        )

        wiki.write_document(input.target_path, doc)
        wiki.save_version(input.target_path, "merge", related=input.source_paths)

        sources_deleted = False
        if input.redirect_sources:
            for source_path in input.source_paths:
                try:
                    wiki.delete_document(source_path)
                    sources_deleted = True
                except WikiStoreError:
                    pass

        return ExecuteMergePlanOutput(
            path=input.target_path,
            action="Merged",
            sources_deleted=sources_deleted,
        )

    # ── Tool: execute_split_plan ─────────────────────────────────────

    def execute_split_plan(input: ExecuteSplitPlanInput) -> ExecuteSplitPlanOutput:
        if wiki.document_exists(input.target_path):
            wiki.save_version(input.target_path, "split")

        original = wiki.read_document(input.target_path)
        new_paths: List[str] = []

        for section in input.sections_to_split:
            new_path = section['new_path']
            _, section_body = parse_frontmatter(section.get('content', ''))

            doc = WikiDocument(
                path=new_path,
                title=new_path.split('/')[-1].replace('_', ' ').title(),
                content=section_body,
                frontmatter={},
                created=datetime.now(),
                modified=datetime.now(),
                tags=original.tags,
                category='/'.join(new_path.split('/')[:-1]) or "general",
                related=[input.target_path],
            )

            wiki.write_document(new_path, doc)
            wiki.save_version(new_path, "split", related=[input.target_path])
            new_paths.append(new_path)

        _, summary_body = parse_frontmatter(input.summary_for_main)
        original.content = summary_body
        original.related = new_paths
        wiki.write_document(input.target_path, original)

        return ExecuteSplitPlanOutput(
            path=input.target_path,
            action="Split",
            new_paths=new_paths,
        )

    # ── Tool: execute_delete_plan ────────────────────────────────────

    def execute_delete_plan(input: ExecuteDeletePlanInput) -> ExecuteDeletePlanOutput:
        if wiki.document_exists(input.target_path):
            wiki.save_version(input.target_path, "delete")

        wiki.delete_document(input.target_path, remove_backlinks=input.remove_backlinks)

        return ExecuteDeletePlanOutput(path=input.target_path, action="Deleted")

    return [
        ToolDefinition(
            name="split_topics",
            description="Split content into multiple topics using LLM analysis. Returns list of separated topic contents.",
            input_model=SplitTopicsInput,
            handler=split_topics,
        ),
        ToolDefinition(
            name="find_existing_document",
            description="Find existing documents via wikilinks and category matching. Returns found paths and content previews.",
            input_model=FindExistingDocumentInput,
            handler=find_existing_document,
        ),
        ToolDefinition(
            name="classify_topic",
            description="Determine which category content belongs to by analyzing the category tree.",
            input_model=ClassifyTopicInput,
            handler=classify_topic,
        ),
        ToolDefinition(
            name="execute_create_plan",
            description="Create a new document with validation, frontmatter stripping, and version tracking.",
            input_model=ExecuteCreatePlanInput,
            handler=execute_create_plan,
        ),
        ToolDefinition(
            name="execute_modify_plan",
            description="Modify existing document (append, prepend, replace_section, append_section_after) with version tracking.",
            input_model=ExecuteModifyPlanInput,
            handler=execute_modify_plan,
        ),
        ToolDefinition(
            name="execute_merge_plan",
            description="Merge multiple documents into one with version tracking. Optionally deletes source documents.",
            input_model=ExecuteMergePlanInput,
            handler=execute_merge_plan,
        ),
        ToolDefinition(
            name="execute_split_plan",
            description="Split document into sub-documents with version tracking. Replaces extracted sections with summary.",
            input_model=ExecuteSplitPlanInput,
            handler=execute_split_plan,
        ),
        ToolDefinition(
            name="execute_delete_plan",
            description="Delete a document with version tracking and optional backlink removal.",
            input_model=ExecuteDeletePlanInput,
            handler=execute_delete_plan,
        ),
    ]


class RecorderWithAgentLoop:
    """Information recording pipeline using AgentLoop.

    LLM analyzes content, explores wiki structure, and decides
    whether to create new documents or modify existing ones.

    Supports:
    - Multi-topic content: Each topic recorded separately
    - Existing document modification: Finds and updates related docs
    - Wikilink support: [[Document Name]] syntax for direct linking
    - Full CRUD operations with version tracking

    Example:
        store = WikiStore("./wiki")
        agent_loop = AgentLoop(provider, tools, system_prompt)
        recorder = RecorderWithAgentLoop(store, agent_loop)

        result = recorder.record("User prefers Python for web development")
        print(result.actions_taken)  # ['Created: users/preferences/python.md']
    """

    def __init__(self, wiki: WikiStore, agent_loop: AgentLoop, logger: Optional[logging.Logger] = None):
        self.wiki = wiki
        self.agent_loop = agent_loop
        self.logger = logger or logging.getLogger(__name__)

        self._register_tools()

    def _register_tools(self) -> None:
        for tool in create_wiki_tools(self.wiki):
            self.agent_loop.registry.register(tool)
        for tool in create_reasoning_tools(self.agent_loop.provider):
            self.agent_loop.registry.register(tool)
        for tool in create_recorder_tools(self.wiki, self.agent_loop.provider, self.logger):
            self.agent_loop.registry.register(tool)

    def record(
        self,
        content: str | Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> RecordResult:
        try:
            if isinstance(content, dict):
                raw_content = content.get('content', str(content))
                content_type = content.get('type', 'structured')
                context = content.get('context', {})
            else:
                raw_content = content
                content_type = metadata.get('type', 'conversation') if metadata else 'conversation'
                context = metadata.get('context', {}) if metadata else {}

            self.logger.debug(f"Recording content: {raw_content[:100]}...")
            self.logger.debug(f"Content type: {content_type}, Context: {context}")

            context_str = f"\nContext: {context}" if context else ""

            user_message = f"""Record this content to the wiki.

Content type: {content_type}{context_str}

Content:
{raw_content}

Analyze this content and record it appropriately:
1. Check if content contains multiple topics (use split_topics)
2. For each topic, search for existing documents before creating new ones
3. Use the appropriate tools to explore, analyze, and record

When finished, respond with: {{"success": true, "actions": [...], "documents": [...]}}"""

            self.agent_loop.reset()
            result = self.agent_loop.run(user_message=user_message)

            if result.truncated:
                self.logger.warning(f"Agent loop truncated after {result.steps} steps")

            actions, affected = self._extract_result(result.output, result.history)

            error = None
            if result.truncated and not actions:
                error = f"Agent loop truncated after {result.steps} steps with no results"

            return RecordResult(
                success=len(actions) > 0,
                actions_taken=actions,
                documents_affected=affected,
                error=error,
            )

        except Exception as e:
            self.logger.error(f"Recording failed: {e}", exc_info=True)
            return RecordResult(
                success=False,
                actions_taken=[],
                documents_affected=[],
                error=str(e)
            )

    def _extract_result(self, output: Any, history: list[dict[str, Any]]) -> tuple[List[str], List[str]]:
        actions: List[str] = []
        affected: set[str] = set()

        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                pass

        if isinstance(output, dict):
            if "actions" in output and isinstance(output["actions"], list):
                actions.extend([a for a in output["actions"] if isinstance(a, str)])
            if "documents" in output and isinstance(output["documents"], list):
                affected.update([d for d in output["documents"] if isinstance(d, str)])

        for msg in history:
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        if data.get("success") and data.get("path"):
                            affected.add(data["path"])
                        # Extract action descriptions
                        action = data.get("action", "")
                        path = data.get("path", "")
                        if action and path:
                            actions.append(f"{action}: {path}")
                except json.JSONDecodeError:
                    pass

        return actions, list(affected)
