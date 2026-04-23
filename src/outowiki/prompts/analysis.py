"""Analysis prompts for information processing."""

ANALYSIS_PROMPT = """Analyze the following input and extract structured information.

Input:
{content}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}
{existing_doc_section}

CATEGORIZATION GUIDELINES (Wikipedia-style, flexible):
1. Category is OPTIONAL - use it when it genuinely helps organize or find information
2. If the content fits an existing category, use it; if not, you may suggest a new one
3. Categories emerge from content naturally - don't force predefined hierarchies
4. Documents can exist at any level - root, nested, or deep hierarchy
5. Naming: lowercase, underscores, descriptive nouns

DEPTH GUIDANCE (when you DO categorize):
- Aim for 3+ levels when content is specific (domain/language/subdomain/topic)
- DON'T: "programming/zod" (too shallow for a specific tool)
- DO: "programming/typescript/validation/zod" (specific and findable)
- When uncertain between depth levels, go deeper rather than shallower
- General knowledge/wisdom can stay at 1-2 levels if no deeper fit exists

EXAMPLES:
- "Flask REST API with SQLAlchemy" → "programming/python/web/flask" (4 levels)
- "Exponential backoff works better than fixed delays" → "programming/patterns/retry" (3 levels) or empty if too general
- "zod for TypeScript validation" → "programming/typescript/validation/zod" (4 levels)

Analyze this input and provide:
1. information_type: What type of information is this? (conversation, agent_internal, external, structured)
2. key_topic: The main topic or concept (1-2 words)
3. specific_content: Summary of the key information
4. existing_relations: Which existing documents might this relate to?
5. temporal_range: Is this time-sensitive? (recent, historical, timeless)
6. confidence_score: How confident are you in the analysis? (0.0-1.0)
7. importance_score: How important is this information? (0.0-1.0)
8. suggested_action: What should we do? MUST be one of these EXACT values: "create", "modify", "merge", "split", "delete" (lowercase)
9. target_documents: Which documents should be affected? Include FULL path if categorized (e.g., "programming/python/web/flask" or just "flask_concepts" for uncategorized)

Respond with valid JSON matching the AnalysisResult schema."""

CONVERSATION_ANALYSIS_PROMPT = """Analyze this conversation and extract knowledge to record.

Conversation:
{content}

Context: {context}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}

CATEGORIZATION GUIDELINES:
1. Categorization is optional - use categories when they help, not by default
2. If existing categories fit, use them; otherwise suggest new ones organically
3. Documents can be organized later if category is uncertain now

DEPTH GUIDANCE (when you DO categorize):
- Aim for 3+ levels for specific content (e.g., "users/alice/preferences/food")
- DON'T: "users/alice/food" (too shallow for a preference topic)
- DO: "users/alice/preferences/food/dietary" (specific and findable)
- General observations can stay shallow or uncategorized

Extract:
1. User preferences or characteristics mentioned
2. Successful approaches or solutions
3. Failed attempts or what to avoid
4. New knowledge or facts learned
5. Action items or follow-ups needed
6. Appropriate category path (if any) for this information - can be empty

Provide analysis as structured JSON."""

LEARNING_ANALYSIS_PROMPT = """Analyze this learning outcome and determine how to record it.

Learning Event:
{content}

Context: {context}
Previous Attempts: {previous_attempts}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}

CATEGORIZATION GUIDELINES:
1. Categorize when it helps organization; skip if too general/uncertain
2. Let categories emerge from the content naturally

DEPTH GUIDANCE (when you DO categorize):
- Aim for 3+ levels for specific learnings (e.g., "agent/learning/patterns/retry")
- DON'T: "agent/retry" (too shallow for a learning pattern)
- DO: "agent/learning/patterns/retry/backoff" (specific and findable)
- General wisdom can stay at 1-2 levels

Determine:
1. What was learned?
2. Is this a success pattern or failure pattern?
3. Should this be a new document or update existing?
4. What category does this belong to? (can be empty if too general)

Provide analysis as structured JSON."""
