"""
Agent Integration Example

This example demonstrates how to integrate OutoWiki into an AI agent
to maintain persistent memory across conversations.
"""

from outowiki import OutoWiki, WikiConfig


class AgentWithMemory:
    """Example agent class that uses OutoWiki for persistent memory."""

    def __init__(self, api_key: str):
        """Initialize the agent with wiki memory."""
        self.wiki = OutoWiki(WikiConfig(
            provider="openai",
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            model="gpt-4",
            max_output_tokens=4000,
            wiki_path="./agent_wiki"
        ))

    def process_turn(self, user_input: str, response: str):
        """Record a conversation turn and any learnings."""
        # Record conversation
        self.wiki.record({
            "type": "conversation",
            "content": f"User: {user_input}\nAgent: {response}"
        })

        # Record learning when user expresses satisfaction
        if "thanks" in user_input.lower() or "great" in user_input.lower():
            self.wiki.record({
                "type": "learning",
                "content": f"Successful approach: {response[:100]}..."
            })

    def before_task(self, task: str):
        """Retrieve relevant context before starting a task."""
        results = self.wiki.search(task)
        if results.paths:
            return self.wiki.get_documents(results.paths)
        return None

    def after_task(self, task: str, outcome: str):
        """Record the outcome of a task for future reference."""
        self.wiki.record({
            "type": "task_outcome",
            "content": f"Task: {task}\nOutcome: {outcome}"
        })


# Usage example
if __name__ == "__main__":
    agent = AgentWithMemory(api_key="your-api-key")

    # Simulate a conversation
    agent.process_turn(
        "I need to build a web API",
        "I recommend using FastAPI with Python. It's modern and well-documented."
    )

    agent.process_turn(
        "Thanks, that worked great!",
        "You're welcome! I'm glad it helped."
    )

    # Before a new task, get relevant context
    context = agent.before_task("building web APIs with Python")
    if context:
        print("Found relevant context from previous interactions")
