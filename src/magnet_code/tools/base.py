from __future__ import annotations
import abc
from dataclasses import dataclass, field
from pathlib import Path
from pydantic import BaseModel, ValidationError
from enum import Enum
from typing import Any

class ToolKind(str, Enum):
    # I/O
    READ = "read"
    WRITE = "write"
    # Execution
    SHELL = "shell"
    NETWORK = "network"
    # Storage
    MEMORY = "memory"
    # Special LLM tools
    MCP = "mcp"
    
    
@dataclass
class ToolInvocation:
    parameters: dict[str, Any]
    cwd: Path
    
    
@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(abc.ABC):
    name: str = "base_tool"
    # Helps the LLM choose the right tools
    description: str = "Base tool"
    kind: ToolKind = ToolKind.READ
    
    def __init__(self) -> None:
        pass
    
    @property
    def schema(self) -> dict[str, Any] | type["BaseModel"]:
        raise NotImplementedError("Tools must define schema property or class attribute")
    
    @abc.abstractmethod
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        pass
    
    def validate_params(self, params: dict[str, Any]) -> list[str]:
        schema = self.schema
        
        if isinstance(params, type) and issubclass(schema, BaseModel):
            try:
                schema(**params)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    # Get locations for this validation error
                    field = ".".join(str(x) for x in error.get("loc", []))
                    msg = error.get("msg", "Validation error")
                    error.append(f"Parameter '{field}': {msg}")
                    
                return errors
            except Exception as e:
                return [str(e)]
        return []