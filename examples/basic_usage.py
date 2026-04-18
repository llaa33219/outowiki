"""
Basic OutoWiki Usage Example

This example demonstrates how to initialize OutoWiki and perform
basic operations: recording information and searching the wiki.
"""

from outowiki import OutoWiki, WikiConfig

# Configuration
config = WikiConfig(
    provider="openai",
    base_url="https://api.openai.com/v1",
    api_key="your-api-key",
    model="gpt-4",
    max_output_tokens=4000,
    wiki_path="./my_wiki"
)

# Initialize
wiki = OutoWiki(config)

# Record information
result = wiki.record("""
User: I prefer Python for web development
Agent: Great! Flask and Django are popular choices.
""")

print(f"Recorded to: {result.path}")

# Search information
results = wiki.search("user programming preferences")
print(f"Found {len(results.paths)} relevant documents:")
for path in results.paths:
    print(f"  - {path}")

# Get document content
if results.paths:
    doc = wiki.get_documents([results.paths[0]])
    print(f"Content snippet: {doc[0].content[:200]}...")
