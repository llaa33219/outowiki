"""Planning prompts for document operations."""

PLANNING_PROMPT = """Based on the analysis, create a plan to update the Wiki.

Analysis:
{analysis_json}

Current Wiki State:
- Documents that might be affected: {affected_docs}
- Document contents (summaries): {doc_summaries}

Create a plan with one or more of these actions:
1. CREATE: New document at appropriate location
2. MODIFY: Update existing document with new information
3. MERGE: Combine multiple related documents
4. SPLIT: Break large document into smaller ones
5. DELETE: Remove obsolete or duplicate content

Consider:
- Avoid duplication (prefer MODIFY over CREATE if similar exists)
- Maintain backlink integrity
- Follow wiki naming conventions (lowercase, underscores)
- Keep documents under 4000 tokens when possible

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
