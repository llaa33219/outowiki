"""Generation prompts for document creation."""

DOCUMENT_GENERATION_PROMPT = """Generate a wiki document based on this information.

Information:
{content}

Metadata:
- Title: {title}
- Category: {category}
- Tags: {tags}
- Related documents: {related}

Create a well-structured markdown document with:
1. YAML frontmatter (title, tags, category, related)
   - NOTE: created and modified dates are automatically managed by the system. Do NOT include them.
2. Clear section headers (## for main sections)
3. Concise, factual content
4. Internal links to related documents using [[path]] format
5. Backlinks section at the bottom

Follow these wiki conventions:
- Use clear, descriptive titles
- Keep paragraphs concise
- Use bullet points for lists
- Include relevant links to related content

TITLE AND TAGS RULES (CRITICAL):
- Title and tags MUST be in English ONLY (no Korean, Chinese, Japanese, etc.)
- Content can be in any language, but title and tags must be English
- Title MUST match the filename (without .md extension)

Title-to-filename conversion rules:
- Convert to lowercase
- Replace spaces with underscores
- Remove special characters (apostrophes, etc.)

Examples:
- Title: "Python Classes" → Filename: "python_classes.md"
- Title: "React Native Camera" → Filename: "react_native_camera.md"

BAD examples (REJECTED):
- Title: "Python 클래스" → REJECTED (must be English)
- Title: "カメラ設定" → REJECTED (must be English)
- Title: "Python Classes" + Filename: "classes.md" → REJECTED (mismatch)

Return the complete document content using the DocumentGeneration tool."""

SUMMARY_GENERATION_PROMPT = """Generate a brief summary of this document.

Document content:
{content}

Create a 2-3 sentence summary that captures:
1. The main topic
2. Key points or findings
3. Relevance to related documents

Keep the summary under 200 tokens.

Return the summary using the SummaryGeneration tool."""

SECTION_GENERATION_PROMPT = """Generate content for this wiki section.

Section title: {section_title}
Context: {context}
Related information: {related_info}

Write clear, factual content for this section. Use:
- Bullet points for lists
- Short paragraphs
- Links to related content where appropriate

Generate the section content now."""
