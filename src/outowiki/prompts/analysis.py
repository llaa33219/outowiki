"""Analysis prompts for information processing."""

ANALYSIS_PROMPT = """Analyze the following input and extract structured information.

Input:
{content}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}

CLASSIFICATION RULES (나무위키/Wikipedia guidelines):
1. Every document MUST belong to a category folder - no exceptions
2. Place document in the MOST SPECIFIC (lowest-level) matching category
3. If no existing category matches, suggest a NEW appropriate category
4. Never leave category empty - use "unassigned" only as last resort
5. Category hierarchy: users/{{username}}/{{subtopic}}, tools/{{toolname}}, knowledge/{{domain}}/{{subtopic}}, agent/{{aspect}}, history/{{type}}
6. Max category depth: 4 levels
7. When a category has 20+ documents, consider creating subcategories
8. One document can belong to multiple categories if genuinely cross-domain
9. Avoid: alphabetical sorting categories, non-defining characteristics, circular references

Analyze this input and provide:
1. information_type: What type of information is this? (conversation, agent_internal, external, structured)
2. key_topic: The main topic or concept (1-2 words)
3. specific_content: Summary of the key information
4. existing_relations: Which existing documents might this relate to?
5. temporal_range: Is this time-sensitive? (recent, historical, timeless)
6. confidence_score: How confident are you in the analysis? (0.0-1.0)
7. importance_score: How important is this information? (0.0-1.0)
8. suggested_action: What should we do? (CREATE, MODIFY, MERGE, SPLIT, DELETE)
9. target_documents: Which documents should be affected? Include FULL category path (e.g., knowledge/programming/python)

Respond with valid JSON matching the AnalysisResult schema."""

CONVERSATION_ANALYSIS_PROMPT = """Analyze this conversation and extract knowledge to record.

Conversation:
{content}

Context: {context}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}

CLASSIFICATION RULES:
1. Every document MUST belong to a category folder
2. Place in MOST SPECIFIC matching category
3. If no match, suggest new appropriate category
4. Category hierarchy: users/{{username}}, tools/{{tool}}, knowledge/{{domain}}, agent/{{aspect}}, history/{{type}}

Extract:
1. User preferences or characteristics mentioned
2. Successful approaches or solutions
3. Failed attempts or what to avoid
4. New knowledge or facts learned
5. Action items or follow-ups needed
6. Appropriate category path for this information

Provide analysis as structured JSON."""

LEARNING_ANALYSIS_PROMPT = """Analyze this learning outcome and determine how to record it.

Learning Event:
{content}

Context: {context}
Previous Attempts: {previous_attempts}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}

CLASSIFICATION RULES:
1. Every document MUST belong to a category folder
2. Place in MOST SPECIFIC matching category (e.g., agent/learning/{{topic}})
3. If no match, suggest new appropriate category
4. Category hierarchy: agent/learning/{{topic}}, knowledge/{{domain}}/{{subtopic}}

Determine:
1. What was learned?
2. Is this a success pattern or failure pattern?
3. Should this be a new document or update existing?
4. What category does this belong to? (full path)

Provide analysis as structured JSON."""
