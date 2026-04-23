"""Tool definitions for agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class ToolDefinition:
    """Defines a tool available to the agent loop."""
    
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[..., Any]
    
    def to_provider_schema(self) -> dict[str, Any]:
        """Convert to provider-specific tool schema."""
        schema = self.input_model.model_json_schema()
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            }
        }


@dataclass
class ToolRegistry:
    """Registry of available tools for the agent loop."""
    
    _tools: dict[str, ToolDefinition] = field(default_factory=dict)
    
    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def to_provider_schemas(self) -> list[dict[str, Any]]:
        """Convert all tools to provider-specific schemas."""
        return [tool.to_provider_schema() for tool in self._tools.values()]
    
    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool with the given arguments."""
        tool = self.get(name)
        if not tool:
            return {"error": f"Unknown tool: {name}"}
        
        try:
            validated_input = tool.input_model.model_validate(arguments)
            result = tool.handler(validated_input)
            
            if isinstance(result, BaseModel):
                return result.model_dump()
            elif isinstance(result, (dict, list, str, int, float, bool, type(None))):
                return result
            else:
                return str(result)
        except Exception as e:
            return {"error": str(e)}
