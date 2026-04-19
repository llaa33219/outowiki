"""Information recording pipeline for OutoWiki."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.content import WikiDocument
from ..models.analysis import AnalysisResult
from ..models.plans import Plan, PlanType, CreatePlan, ModifyPlan, MergePlan, SplitPlan, DeletePlan
from ..core.store import WikiStore
from .agent import InternalAgent
from ..core.exceptions import WikiStoreError
from ..utils.markdown import extract_sections


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


class Recorder:
    """Information recording pipeline.

    Processes raw content through analysis, planning, and execution
    to update the wiki with new information.

    Pipeline:
        1. Analyze: Extract structured information from raw input
        2. Plan: Determine what wiki operations to perform
        3. Execute: Apply the plans to update documents

    Example:
        store = WikiStore("./wiki")
        agent = InternalAgent(provider)
        recorder = Recorder(store, agent)

        result = recorder.record("User prefers Python for web development")
        print(result.actions_taken)  # ['Created: users/preferences/python.md']
    """

    def __init__(self, wiki: WikiStore, agent: InternalAgent, logger: Optional[logging.Logger] = None):
        """Initialize recorder.

        Args:
            wiki: Wiki store for document operations
            agent: Internal agent for LLM processing
            logger: Optional logger for debug output
        """
        self.wiki = wiki
        self.agent = agent
        self.logger = logger or logging.getLogger(__name__)

    def record(
        self,
        content: str | Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> RecordResult:
        """Record information to the wiki.

        Args:
            content: Raw content (string or structured dict)
            metadata: Optional metadata (type, context, etc.)

        Returns:
            RecordResult with actions taken
        """
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

            analysis = self._analyze(raw_content, content_type, context)
            self.logger.debug(f"Analysis result: {analysis}")

            plans = self._plan(analysis)
            self.logger.debug(f"Generated {len(plans)} plans: {[p.plan_type for p in plans]}")

            result = self._execute(plans)
            self.logger.debug(f"Execution result: {result}")

            return result

        except Exception as e:
            self.logger.error(f"Recording failed: {e}", exc_info=True)
            return RecordResult(
                success=False,
                actions_taken=[],
                documents_affected=[],
                error=str(e)
            )

    def _analyze(
        self,
        content: str,
        content_type: str,
        context: Dict[str, Any]
    ) -> AnalysisResult:
        """Analyze raw content.

        Args:
            content: Raw input content
            content_type: Type of content
            context: Additional context

        Returns:
            AnalysisResult with extracted information
        """
        self.logger.debug("Starting content analysis...")
        categories = self._get_categories()
        recent_docs = self._get_recent_docs()

        context.update({
            'categories': categories,
            'recent_docs': recent_docs
        })
        self.logger.debug(f"Context for analysis: categories={len(categories)}, recent_docs={len(recent_docs)}")

        analysis = self.agent.analyze(content, content_type, context)
        self.logger.debug(f"Analysis completed: type={analysis.information_type}, action={analysis.suggested_action}")
        return analysis

    def _plan(self, analysis: AnalysisResult) -> List[Plan]:
        """Create modification plans.

        Args:
            analysis: Analysis result from _analyze()

        Returns:
            List of Plan objects
        """
        self.logger.debug("Creating modification plans...")
        affected_docs = {}
        for doc_path in analysis.target_documents:
            try:
                doc = self.wiki.read_document(doc_path)
                affected_docs[doc_path] = doc.content[:500]
                self.logger.debug(f"Affected document: {doc_path}")
            except WikiStoreError:
                self.logger.debug(f"Document not found: {doc_path}")

        plans = self.agent.plan(analysis, affected_docs)
        self.logger.debug(f"Plans created: {len(plans)} plans")
        return plans

    def _execute(self, plans: List[Plan]) -> RecordResult:
        """Execute modification plans.

        Args:
            plans: List of plans to execute

        Returns:
            RecordResult with actions taken
        """
        self.logger.debug(f"Executing {len(plans)} plans...")
        actions = []
        affected = []

        for i, plan in enumerate(plans, 1):
            self.logger.debug(f"Executing plan {i}/{len(plans)}: {plan.plan_type}")
            try:
                if plan.plan_type == PlanType.CREATE:
                    assert isinstance(plan, CreatePlan)
                    self.logger.debug(f"Creating document: {plan.target_path}")
                    self._execute_create(plan)
                    actions.append(f"Created: {plan.target_path}")
                    affected.append(plan.target_path)

                elif plan.plan_type == PlanType.MODIFY:
                    assert isinstance(plan, ModifyPlan)
                    self.logger.debug(f"Modifying document: {plan.target_path}")
                    self._execute_modify(plan)
                    actions.append(f"Modified: {plan.target_path}")
                    affected.append(plan.target_path)

                elif plan.plan_type == PlanType.MERGE:
                    assert isinstance(plan, MergePlan)
                    self.logger.debug(f"Merging documents: {plan.source_paths} -> {plan.target_path}")
                    result = self._execute_merge(plan)
                    actions.append(f"Merged: {result}")
                    affected.extend(plan.source_paths)
                    affected.append(plan.target_path)

                elif plan.plan_type == PlanType.SPLIT:
                    assert isinstance(plan, SplitPlan)
                    self.logger.debug(f"Splitting document: {plan.target_path}")
                    result = self._execute_split(plan)
                    actions.append(f"Split: {result}")
                    affected.append(plan.target_path)

                elif plan.plan_type == PlanType.DELETE:
                    assert isinstance(plan, DeletePlan)
                    self.logger.debug(f"Deleting document: {plan.target_path}")
                    self._execute_delete(plan)
                    actions.append(f"Deleted: {plan.target_path}")
                    affected.append(plan.target_path)

                self.logger.debug(f"Plan {i} executed successfully")

            except Exception as e:
                self.logger.error(f"Plan {i} failed: {e}", exc_info=True)
                actions.append(f"Failed {plan.plan_type}: {e}")

        self.logger.debug(f"Execution completed: {len(actions)} actions, {len(affected)} documents affected")
        return RecordResult(
            success=len(actions) > 0,
            actions_taken=actions,
            documents_affected=affected
        )

    def _execute_create(self, plan: CreatePlan) -> None:
        category = plan.metadata.category
        target_path = plan.target_path
        
        if not category:
            category = self.wiki.default_category
            self.logger.debug(f"Category is empty, using default: {category}")
        
        if '/' not in target_path:
            target_path = f"{category}/{target_path}"
            self.logger.debug(f"Target path has no folder, using: {target_path}")
        
        content = self.agent.generate_document(
            content=plan.content,
            title=plan.metadata.title,
            category=category,
            tags=plan.metadata.tags,
            related=plan.metadata.related
        )

        doc = WikiDocument(
            path=target_path,
            title=plan.metadata.title,
            content=content,
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=plan.metadata.tags,
            category=category,
            related=plan.metadata.related
        )

        self.wiki.write_document(target_path, doc)
        self.wiki.save_version(target_path, "create")

    def _execute_modify(self, plan: ModifyPlan) -> None:
        """Execute a modify plan."""
        if self.wiki.document_exists(plan.target_path):
            self.wiki.save_version(plan.target_path, "modify")

        doc = self.wiki.read_document(plan.target_path)

        for mod in plan.modifications:
            section = mod.get('section')
            operation = mod.get('operation', 'append')
            content = mod.get('content', '')

            if operation == 'append':
                doc.content += f"\n\n{content}"
            elif operation == 'prepend':
                doc.content = f"{content}\n\n{doc.content}"
            elif operation == 'replace_section':
                sections = extract_sections(doc.content)
                target_level = None
                for sec in sections:
                    if sec['title'] == section:
                        target_level = int(sec['level'])
                        break

                if target_level is not None:
                    lines = doc.content.split('\n')
                    new_lines = []
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
                                new_lines.append(content)
                                continue
                            elif in_target:
                                in_target = False

                        if not in_target:
                            new_lines.append(line)

                    doc.content = '\n'.join(new_lines)

        self.wiki.write_document(plan.target_path, doc)

    def _execute_merge(self, plan: MergePlan) -> str:
        """Execute a merge plan."""
        for source_path in plan.source_paths:
            if self.wiki.document_exists(source_path):
                self.wiki.save_version(source_path, "merge")

        merged_content = plan.merged_content

        doc = WikiDocument(
            path=plan.target_path,
            title=plan.target_path.split('/')[-1].replace('_', ' ').title(),
            content=merged_content,
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category='/'.join(plan.target_path.split('/')[:-1]),
            related=plan.source_paths
        )

        self.wiki.write_document(plan.target_path, doc)
        self.wiki.save_version(plan.target_path, "merge", related=plan.source_paths)

        if plan.redirect_sources:
            for source_path in plan.source_paths:
                try:
                    self.wiki.delete_document(source_path)
                except WikiStoreError:
                    pass

        return f"{plan.source_paths} -> {plan.target_path}"

    def _execute_split(self, plan: SplitPlan) -> str:
        """Execute a split plan."""
        if self.wiki.document_exists(plan.target_path):
            self.wiki.save_version(plan.target_path, "split")

        original = self.wiki.read_document(plan.target_path)

        new_paths = []
        for section in plan.sections_to_split:
            new_path = section['new_path']
            new_content = section.get('content', '')

            doc = WikiDocument(
                path=new_path,
                title=new_path.split('/')[-1].replace('_', ' ').title(),
                content=new_content,
                frontmatter={},
                created=datetime.now(),
                modified=datetime.now(),
                tags=original.tags,
                category='/'.join(new_path.split('/')[:-1]),
                related=[plan.target_path]
            )

            self.wiki.write_document(new_path, doc)
            self.wiki.save_version(new_path, "split", related=[plan.target_path])
            new_paths.append(new_path)

        original.content = plan.summary_for_main
        original.related = new_paths
        self.wiki.write_document(plan.target_path, original)

        return f"{plan.target_path} -> {new_paths}"

    def _execute_delete(self, plan: DeletePlan) -> None:
        """Execute a delete plan."""
        if self.wiki.document_exists(plan.target_path):
            self.wiki.save_version(plan.target_path, "delete")

        self.wiki.delete_document(
            plan.target_path,
            remove_backlinks=plan.remove_backlinks
        )

    def _get_categories(self, max_depth: int = 4) -> List[str]:
        categories = []
        self._collect_categories("", categories, 0, max_depth)
        return categories

    def _collect_categories(self, path: str, categories: List[str], depth: int, max_depth: int) -> None:
        if depth >= max_depth:
            return
        try:
            content = self.wiki.list_folder(path)
            for folder in content['folders']:
                folder_path = f"{path}/{folder}" if path else folder
                categories.append(folder_path)
                self._collect_categories(folder_path, categories, depth + 1, max_depth)
        except WikiStoreError:
            pass

    def _get_recent_docs(self) -> List[str]:
        """Get list of recently modified documents."""
        try:
            md_files = list(self.wiki.root.rglob("*.md"))
            md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            docs = []
            for f in md_files[:10]:
                rel = f.relative_to(self.wiki.root)
                path_str = str(rel)
                if path_str.endswith('.md'):
                    path_str = path_str[:-3]
                docs.append(path_str)
            return docs
        except Exception:
            return []
