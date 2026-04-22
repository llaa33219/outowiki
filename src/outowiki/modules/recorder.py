"""Information recording pipeline for OutoWiki."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.content import WikiDocument
from ..models.analysis import AnalysisResult
from ..models.plans import Plan, PlanType, CreatePlan, ModifyPlan, MergePlan, SplitPlan, DeletePlan
from ..core.store import WikiStore
from .agent import InternalAgent
from ..core.exceptions import WikiStoreError
from ..utils.markdown import extract_sections, parse_frontmatter


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

            topics = self._split_topics(raw_content)
            if len(topics) > 1:
                self.logger.debug(f"Multiple topics detected: {len(topics)}")
                all_actions = []
                all_affected = []
                
                for i, topic in enumerate(topics, 1):
                    self.logger.debug(f"Processing topic {i}/{len(topics)}: {topic[:50]}...")
                    topic_result = self._process_single_topic(topic, content_type, context.copy())
                    all_actions.extend(topic_result.actions_taken)
                    all_affected.extend(topic_result.documents_affected)
                
                return RecordResult(
                    success=len(all_actions) > 0,
                    actions_taken=all_actions,
                    documents_affected=list(set(all_affected))
                )
            
            existing_doc_path = self._find_existing_document(raw_content)
            if existing_doc_path:
                self.logger.debug(f"Found existing document: {existing_doc_path}")
                existing_doc = self.wiki.read_document(existing_doc_path)
                context['existing_doc_path'] = existing_doc_path
                context['existing_doc_content'] = existing_doc.content

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

    def _classify_topic(self, content: str) -> Optional[str]:
        category_tree = self._explore_category_tree()
        
        def format_tree(tree: Dict[str, Any], indent: int = 0) -> List[str]:
            lines: List[str] = []
            if tree['category']:
                lines.append("  " * indent + f"- {tree['category']}/ ({len(tree['files'])} files)")
            for sub in tree['subcategories']:
                lines.extend(format_tree(sub, indent + 1))
            return lines
        
        tree_lines = format_tree(category_tree)
        tree_str = "\n".join(tree_lines) if tree_lines else "(빈 분류 트리 - 새 분류를 생성하세요)"
        
        prompt = f"""Analyze this content and determine which category it belongs to.

Content: {content[:500]}

Available category tree:
{tree_str}

Determine the SINGLE most specific category this content belongs to.
If no existing category fits well, suggest a NEW category path (e.g., "programming/python/web").

Return the category path (e.g., "programming/python/web")."""
        
        try:
            result: Any = self.agent._call_with_schema(prompt, type('CategoryResult', (), {'category': ''}))
            if hasattr(result, 'category') and result.category:
                self._create_category_if_needed(result.category)
                return str(result.category)
        except Exception as e:
            self.logger.debug(f"Topic classification failed: {e}")
        
        return None

    def _find_document_in_category(self, category: str, content: str) -> Optional[str]:
        try:
            folder_content = self.wiki.list_folder(category)
            if folder_content['files']:
                self.logger.debug(f"Found documents in category {category}: {folder_content['files']}")
                return f"{category}/{folder_content['files'][0]}"
        except WikiStoreError:
            pass
        
        subcategories = [c for c in self._get_categories() if c.startswith(category + '/')]
        for subcat in subcategories:
            try:
                folder_content = self.wiki.list_folder(subcat)
                if folder_content['files']:
                    self.logger.debug(f"Found documents in subcategory {subcat}: {folder_content['files']}")
                    return f"{subcat}/{folder_content['files'][0]}"
            except WikiStoreError:
                continue
        
        return None

    def _parse_wikilinks(self, content: str) -> List[str]:
        pattern = r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]'
        links = re.findall(pattern, content)
        self.logger.debug(f"Parsed wikilinks: {links}")
        return links

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
                affected_docs[doc_path] = doc.content
                self.logger.debug(f"Affected document: {doc_path} (full content: {len(doc.content)} chars)")
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
        
        if category and '/' not in target_path:
            target_path = f"{category}/{target_path}"
            self.logger.debug(f"Using category as path prefix: {target_path}")
        elif not category:
            self.logger.debug(f"No category specified, using target_path as-is: {target_path}")
        
        generated_content = self.agent.generate_document(
            content=plan.content,
            title=plan.title,
            category=category or "",
            tags=plan.metadata.tags,
            related=plan.metadata.related
        )

        _, body_content = parse_frontmatter(generated_content)

        doc = WikiDocument(
            path=target_path,
            title=plan.title,
            content=body_content,
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
            _, mod_body = parse_frontmatter(mod.get('content', ''))

            if operation == 'append':
                doc.content += f"\n\n{mod_body}"
            elif operation == 'prepend':
                doc.content = f"{mod_body}\n\n{doc.content}"
            elif operation == 'append_section_after':
                if section:
                    doc.content = self._append_section_after(doc.content, section, mod_body)
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
                                new_lines.append(mod_body)
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

        _, merged_body = parse_frontmatter(plan.merged_content)

        doc = WikiDocument(
            path=plan.target_path,
            title=plan.target_path.split('/')[-1].replace('_', ' ').title(),
            content=merged_body,
            frontmatter={},
            created=datetime.now(),
            modified=datetime.now(),
            tags=[],
            category='/'.join(plan.target_path.split('/')[:-1]) or None,
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
            _, section_body = parse_frontmatter(section.get('content', ''))

            doc = WikiDocument(
                path=new_path,
                title=new_path.split('/')[-1].replace('_', ' ').title(),
                content=section_body,
                frontmatter={},
                created=datetime.now(),
                modified=datetime.now(),
                tags=original.tags,
                category='/'.join(new_path.split('/')[:-1]) or None,
                related=[plan.target_path]
            )

            self.wiki.write_document(new_path, doc)
            self.wiki.save_version(new_path, "split", related=[plan.target_path])
            new_paths.append(new_path)

        _, summary_body = parse_frontmatter(plan.summary_for_main)
        original.content = summary_body
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
        categories: List[str] = []
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

    def _find_existing_document(self, content: str) -> Optional[str]:
        wikilinks = self._parse_wikilinks(content)
        for link in wikilinks:
            normalized = link.replace(' ', '_').lower()
            if self.wiki.document_exists(normalized):
                self.logger.debug(f"Found via wikilink: {normalized}")
                return normalized
            if self.wiki.document_exists(link):
                self.logger.debug(f"Found via wikilink: {link}")
                return link

        topic_category = self._classify_topic(content)
        if topic_category:
            doc_path = self._find_document_in_category(topic_category, content)
            if doc_path:
                return doc_path

        return None

    def _extract_keywords(self, content: str) -> List[str]:
        content_lower = content.lower()
        
        known_terms = [
            'camera', 'react native', 'expo', 'ios', 'android',
            'python', 'javascript', 'typescript', 'flask', 'django',
            'api', 'rest', 'graphql', 'database', 'sql', 'mongodb',
            'auth', 'jwt', 'oauth', 'security', 'performance',
            'error', 'bug', 'crash', 'debug', 'test',
        ]
        
        found_keywords = []
        for term in known_terms:
            if term in content_lower:
                found_keywords.append(term)
        
        words = re.findall(r'\b[a-z]{4,}\b', content_lower)
        stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'will', 'would', 'could', 'should'}
        meaningful_words = [w for w in words if w not in stop_words]
        
        word_freq: Dict[str, int] = {}
        for word in meaningful_words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        found_keywords.extend([w for w, _ in top_words])
        
        return list(set(found_keywords))

    def _category_matches(self, category: str, keywords: List[str]) -> bool:
        category_lower = category.lower()
        category_parts = category_lower.split('/')
        
        for keyword in keywords:
            for part in category_parts:
                if keyword in part or part in keyword:
                    return True
        return False

    def _append_section_after(self, content: str, target_section: str, new_content: str) -> str:
        lines = content.split('\n')
        new_lines = []
        inserted = False
        target_level = None
        
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

    def _split_topics(self, content: str) -> List[str]:
        llm_topics = self._split_topics_with_llm(content)
        if llm_topics and len(llm_topics) > 1:
            return llm_topics
        return [content]

    def _split_topics_with_llm(self, content: str) -> Optional[List[str]]:
        prompt = f"""Analyze this text and identify distinct topics mixed together.

Text:
{content[:2000]}

Identify ALL distinct topics/subjects in this text. Each topic should be a separate block of content.

Return a JSON object with a "topics" array containing the separated content blocks.
Example: {{"topics": ["Topic 1 content...", "Topic 2 content...", "Topic 3 content..."]}}"""
        
        try:
            result = self.agent._call_with_schema(prompt, type('TopicSplitResult', (), {'topics': []}))
            if hasattr(result, 'topics') and result.topics:
                topics = [t.strip() for t in result.topics if t.strip() and len(t.strip()) > 20]
                if len(topics) > 1:
                    self.logger.debug(f"LLM split into {len(topics)} topics")
                    return topics
        except Exception as e:
            self.logger.debug(f"LLM topic splitting failed: {e}")
        
        return None

    def _process_single_topic(self, content: str, content_type: str, context: Dict[str, Any]) -> RecordResult:
        existing_doc_path = self._find_existing_document(content)
        if existing_doc_path:
            self.logger.debug(f"Found existing document: {existing_doc_path}")
            existing_doc = self.wiki.read_document(existing_doc_path)
            context['existing_doc_path'] = existing_doc_path
            context['existing_doc_content'] = existing_doc.content

        analysis = self._analyze(content, content_type, context)
        self.logger.debug(f"Analysis result: {analysis}")

        plans = self._plan(analysis)
        self.logger.debug(f"Generated {len(plans)} plans: {[p.plan_type for p in plans]}")

        result = self._execute(plans)
        self.logger.debug(f"Execution result: {result}")

        return result

    def _explore_category_tree(self, category: str = "", depth: int = 0, max_depth: int = 3) -> Dict[str, Any]:
        if depth > max_depth:
            return {'category': category, 'files': [], 'subcategories': [], 'truncated': True}
        
        try:
            folder_content = self.wiki.list_folder(category)
            result: Dict[str, Any] = {
                'category': category,
                'files': folder_content.get('files', []),
                'subcategories': [],
                'truncated': False
            }
            
            for subfolder in folder_content.get('folders', []):
                subcategory_path = f"{category}/{subfolder}" if category else subfolder
                subcategory_result = self._explore_category_tree(subcategory_path, depth + 1, max_depth)
                result['subcategories'].append(subcategory_result)
            
            self.logger.debug(f"Explored category {category}: {len(result['files'])} files, {len(result['subcategories'])} subcategories")
            return result
            
        except WikiStoreError:
            return {'category': category, 'files': [], 'subcategories': [], 'truncated': False}

    def _create_category_if_needed(self, category: str) -> bool:
        if not category:
            return False
        
        try:
            self.wiki.list_folder(category)
            return False
        except WikiStoreError:
            pass
        
        parts = category.split('/')
        current_path = ""
        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            try:
                self.wiki.list_folder(current_path)
            except WikiStoreError:
                self.logger.debug(f"Creating category folder: {current_path}")
                self.wiki.create_folder(current_path)
        
        doc_path = f"{category}/README.md"
        if not self.wiki.document_exists(doc_path):
            category_name = category.split('/')[-1]
            doc = WikiDocument(
                path=doc_path,
                title=category_name,
                content=f"# {category_name}\n\n이 분류는 {category_name}에 속하는 문서들을 포함합니다.",
                frontmatter={},
                created=datetime.now(),
                modified=datetime.now(),
                tags=[],
                category=category,
                related=[]
            )
            self.wiki.write_document(doc_path, doc)
            self.logger.debug(f"Created category README: {doc_path}")
        
        return True
