"""Analysis prompts for information processing."""

ANALYSIS_PROMPT = """Analyze the following input and extract structured information.

Input:
{content}

Current Wiki State:
- Existing categories: {categories}
- Recent documents: {recent_docs}

Analyze this input and provide:
1. information_type: What type of information is this? (conversation, agent_internal, external, structured)
2. key_topic: The main topic or concept (1-2 words)
3. specific_content: Summary of the key information
4. existing_relations: Which existing documents might this relate to?
5. temporal_range: Is this time-sensitive? (recent, historical, timeless)
6. confidence_score: How confident are you in the analysis? (0.0-1.0)
7. importance_score: How important is this information? (0.0-1.0)
8. suggested_action: What should we do? (CREATE, MODIFY, MERGE, SPLIT, DELETE)
9. target_documents: Which documents should be affected?

Respond with valid JSON matching the AnalysisResult schema."""

CONVERSATION_ANALYSIS_PROMPT = """Analyze this conversation and extract knowledge to record.

Conversation:
{content}

Context: {context}

Extract:
1. User preferences or characteristics mentioned
2. Successful approaches or solutions
3. Failed attempts or what to avoid
4. New knowledge or facts learned
5. Action items or follow-ups needed

Provide analysis as structured JSON."""

LEARNING_ANALYSIS_PROMPT = """Analyze this learning outcome and determine how to record it.

Learning Event:
{content}

Context: {context}
Previous Attempts: {previous_attempts}

Determine:
1. What was learned?
2. Is this a success pattern or failure pattern?
3. Should this be a new document or update existing?
4. What category does this belong to?

Provide analysis as structured JSON."""
