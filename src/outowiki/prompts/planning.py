"""Planning prompts for document operations."""

PLANNING_PROMPT = """Based on the analysis, create a plan to update the Wiki.

Analysis:
{analysis_json}

Current Wiki State:
- Documents that might be affected: {affected_docs}
- Document contents (summaries): {doc_summaries}

PLANNING GUIDELINES (Wikipedia-style, flexible):
1. target_path can include category hierarchy OR just a document name - both are valid
2. Categories emerge from content - don't force predefined structures
3. Documents can live at any depth: root level, nested, or deeply categorized
4. Naming: lowercase, underscores, descriptive
5. If category is uncertain, use descriptive filename at current level

DEPTH GUIDANCE (when you DO categorize):
- Aim for 3+ levels for specific content (domain/language/subdomain/topic)
- DON'T: "programming/zod" (too shallow for a specific tool)
- DO: "programming/typescript/validation/zod" (specific and findable)
- When uncertain between depth levels, go deeper rather than shallower

CRITICAL REQUIREMENTS:
- metadata.title is REQUIRED for ALL actions - you MUST provide a descriptive title
- Title should be human-readable (e.g., "React Native Camera Setup" not "react_native_camera")
- Title is used as the document's display name
- Title MUST be CONSISTENT with filename (without .md extension)
- plans MUST be an array of plan objects, NOT a JSON string

TITLE AND FILENAME CONSISTENCY RULES:
- File name (without .md) should be derived from the title
- Title should match the file name (with underscores converted to spaces)
- This ensures consistency between file system and display

Examples (title → filename):
- Title: "Python Classes" → Filename: "python_classes.md"
- Title: "React Native Camera" → Filename: "react_native_camera.md"
- Title: "Alice's Preferences" → Filename: "alices_preferences.md"
- Title: "Aluminum" → Filename: "aluminum.md"

Rules for converting title to filename:
- Convert to lowercase
- Replace spaces with underscores
- Remove special characters (apostrophes, etc.)
- Keep it concise but descriptive

ENGLISH-ONLY RULE:
- Title MUST be written in English ONLY
- Tags MUST be written in English ONLY
- Do NOT use Korean, Chinese, Japanese, or any non-English characters
- Content can be in any language, but title and tags must be English

GOOD examples (title → filename):
- "Python Classes" → "python_classes.md"
- "React Native Camera" → "react_native_camera.md"
- "Decorators in Python" → "decorators_in_python.md"
- "Aluminum Properties" → "aluminum_properties.md"

BAD examples (inconsistent):
- Title: "Python Classes" → Filename: "classes.md" (missing context)
- Title: "React Native Camera" → Filename: "camera.md" (too generic)
- Title: "Decorators" → Filename: "python_decorators.md" (mismatch)

BAD examples (non-English - REJECTED):
- Title: "Python 클래스" → REJECTED (must be English)
- Title: "カメラ設定" → REJECTED (must be English)
- Tags: ["python", "데코레이터"] → REJECTED (must be English)

CREATE PLAN - REQUIRED FIELDS:
When creating a new document, you MUST provide ALL of these fields:
- target_path: Path where document will be created (e.g., "programming/python/decorators")
- reason: Why this document is being created
- content: The FULL content of the new document in markdown format
- title: Human-readable title (e.g., "Python Decorators Guide")
- metadata: Object with title, tags, category, related documents

Example CREATE plan:
{{
  "plan_type": "create",
  "target_path": "programming/python/decorators",
  "reason": "New information about Python decorators",
  "content": "# Python Decorators\\n\\nDecorators are a powerful feature...",
  "title": "Python Decorators Guide",
  "metadata": {{
    "title": "Python Decorators Guide",
    "tags": ["python", "decorators"],
    "category": "programming/python",
    "related": []
  }}
}}

MODIFY PLAN - REQUIRED FIELDS:
When modifying an existing document:
- target_path: Path of document to modify
- reason: Why this modification is needed
- modifications: Array of changes to apply (each with section, operation, content)

DELETE PLAN - REQUIRED FIELDS:
- target_path: Path of document to delete
- reason: Why this document should be deleted

Create a plan with one or more of these actions:
1. CREATE: New document at appropriate location (can be at root or in any folder)
2. MODIFY: Update existing document with new information
3. MERGE: Combine multiple related documents
4. SPLIT: Break large document into smaller ones
5. DELETE: Remove obsolete or duplicate content

Consider:
- Avoid duplication (prefer MODIFY over CREATE if similar exists)
- Maintain backlink integrity
- Follow wiki naming conventions (lowercase, underscores)
- Keep documents under 4000 tokens when possible
- Choose meaningful paths that help future discovery

You MUST use the provided tool to return the plan. Do NOT respond with plain text or JSON."""

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
