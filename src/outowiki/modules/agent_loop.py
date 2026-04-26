"""Agent loop with tool-calling and conversation history."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from ..providers.base import LLMProvider
from .tools import ToolDefinition, ToolRegistry


@dataclass
class AgentResult:
    """Result from agent loop execution."""
    
    output: Any
    steps: int
    truncated: bool = False
    history: list[dict[str, Any]] = field(default_factory=list)


class AgentLoop:
    """Unified agent loop with tool-calling and conversation history.
    
    Manages a conversation with the LLM, executing tools as the LLM requests them
    until either the LLM returns a final answer or max iterations is reached.
    """

    def __init__(
        self,
        provider: LLMProvider,
        tools: list[ToolDefinition],
        system_prompt: str,
        max_iterations: int = 80,
        logger: logging.Logger | None = None,
    ):
        self.provider = provider
        self.registry = ToolRegistry()
        for tool in tools:
            self.registry.register(tool)
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.logger = logger or logging.getLogger(__name__)
        self._history: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Reset conversation history."""
        self._history = []

    def run(
        self,
        user_message: str,
        *,
        context: dict[str, Any] | None = None,
        terminal_tools: set[str] | None = None,
    ) -> AgentResult:
        """Execute the agent loop until completion or max iterations.
        
        Args:
            user_message: Initial user message
            context: Optional context to inject into system prompt
            terminal_tools: Set of tool names that signal completion
            
        Returns:
            AgentResult with output and execution history
        """
        system_prompt = self.system_prompt
        if context:
            system_prompt = system_prompt.format(**context)
        
        self._history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        
        terminal_tools = terminal_tools or set()
        
        for step in range(self.max_iterations):
            self.logger.debug(f"Agent loop step {step + 1}/{self.max_iterations}")
            
            try:
                response = self.provider.chat_with_tools(
                    messages=self._history,
                    tools=self.registry.to_provider_schemas(),
                )
            except Exception as e:
                self.logger.error(f"Provider call failed: {e}")
                return AgentResult(
                    output=None,
                    steps=step + 1,
                    truncated=True,
                    history=list(self._history),
                )
            
            if not response.tool_calls:
                self.logger.debug("No tool calls, returning content")
                return AgentResult(
                    output=response.content,
                    steps=step + 1,
                    history=list(self._history),
                )
            
            self._history.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in response.tool_calls
                ],
            })
            
            for tool_call in response.tool_calls:
                self.logger.debug(f"Executing tool: {tool_call.name}")
                
                if tool_call.parsed_arguments:
                    arguments = tool_call.parsed_arguments
                else:
                    try:
                        arguments = json.loads(tool_call.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                
                result = self.registry.execute(tool_call.name, arguments)
                
                result_content = json.dumps(result) if not isinstance(result, str) else result
                
                self._history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_content,
                })
                
                if tool_call.name in terminal_tools:
                    self.logger.debug(f"Terminal tool {tool_call.name} called, returning")
                    return AgentResult(
                        output=result,
                        steps=step + 1,
                        history=list(self._history),
                    )
        
        self.logger.warning(f"Max iterations ({self.max_iterations}) reached")
        return AgentResult(
            output=None,
            steps=self.max_iterations,
            truncated=True,
            history=list(self._history),
        )

    @property
    def history(self) -> list[dict[str, Any]]:
        """Get current conversation history."""
        return self._history
