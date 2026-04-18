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
1. YAML frontmatter (title, created, modified, tags, category, related)
2. Clear section headers (## for main sections)
3. Concise, factual content
4. Internal links to related documents using [[path]] format
5. Backlinks section at the bottom

Follow these wiki conventions:
- Use clear, descriptive titles
- Keep paragraphs concise
- Use bullet points for lists
- Include relevant links to related content

Generate the complete document now."""

SUMMARY_GENERATION_PROMPT = """Generate a brief summary of this document.

Document content:
{content}

Create a 2-3 sentence summary that captures:
1. The main topic
2. Key points or findings
3. Relevance to related documents

Keep the summary under 200 tokens."""

SECTION_GENERATION_PROMPT = """Generate content for this wiki section.

Section title: {section_title}
Context: {context}
Related information: {related_info}

Write clear, factual content for this section. Use:
- Bullet points for lists
- Short paragraphs
- Links to related content where appropriate

Generate the section content now."""
