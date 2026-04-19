"""Planning prompts for document operations."""

PLANNING_PROMPT = """Based on the analysis, create a plan to update the Wiki.

Analysis:
{analysis_json}

Current Wiki State:
- Documents that might be affected: {affected_docs}
- Document contents (summaries): {doc_summaries}

CLASSIFICATION RULES (나무위키/Wikipedia guidelines):
1. Every document MUST be placed in a category folder - NEVER at root level
2. target_path MUST include FULL category hierarchy (e.g., "knowledge/programming/python/oop")
3. Use MOST SPECIFIC category that matches (lowest level in hierarchy)
4. If parent category has 20+ documents, CREATE subcategory for organization
5. Max depth: 4 levels. If deeper needed, restructure hierarchy
6. Category naming: lowercase, underscores, singular nouns
7. Example hierarchy:
   - users/{{username}}/profile.md
   - users/{{username}}/preferences/{{topic}}.md
   - tools/{{toolname}}/usage.md
   - knowledge/{{domain}}/{{subdomain}}/{{topic}}.md
   - agent/{{aspect}}/{{detail}}.md
   - history/{{type}}/{{date}}.md

Create a plan with one or more of these actions:
1. CREATE: New document at appropriate location (MUST include full category path)
2. MODIFY: Update existing document with new information
3. MERGE: Combine multiple related documents
4. SPLIT: Break large document into smaller ones
5. DELETE: Remove obsolete or duplicate content

Consider:
- Avoid duplication (prefer MODIFY over CREATE if similar exists)
- Maintain backlink integrity
- Follow wiki naming conventions (lowercase, underscores)
- Keep documents under 4000 tokens when possible
- Ensure target_path has proper category hierarchy
- Consider creating subcategories if parent is crowded (20+ docs)

Respond with a list of Plan objects in JSON format."""

MERGE_PLANNING_PROMPT = """Plan how to merge these documents.

Documents to merge:
{documents_json}

Reason for merge: {reason}

Determine:
1. Which document should be the primary (target)?
2. How should content be organized in the merged document?
3. What backlinks need updating?
4. Should source documents become redirects?

Provide merge plan as structured JSON."""

SPLIT_PLANNING_PROMPT = """Plan how to split this document.

Document:
{document_json}

Reason for split: {reason}

Determine:
1. Which sections should become separate documents?
2. What should the new document names be?
3. What summary should remain in the main document?
4. How should backlinks be updated?

Provide split plan as structured JSON."""
