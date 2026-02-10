from __future__ import annotations
import abc
from dataclasses import dataclass, field
from pathlib import Path
from pydantic import BaseModel, ValidationError
from pydantic.json_schema import model_json_schema
from enum import Enum
from typing import Any

from magnet_code.config.config import Config


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
class ToolConfirmation:
    tool_name: str
    params: dict[str, Any]
    description: str


@dataclass
class FileDiff:
    path: Path
    old_content: str
    new_content: str

    is_new_file: bool = False
    is_deletion: bool = False

    def create_diff(self) -> str:
        import difflib

        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        # We need to add a new line at the end for difflib to work
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"

        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        old_name = "/dev/null" if self.is_new_file else str(self.path)
        new_name = "/dev/null" if self.is_deletion else str(self.path)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_name,
            tofile=new_name,
        )

        return "".join(diff)


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Fields useful for tool implementations
    truncated: bool = False
    diff: FileDiff | None = None
    exit_code: int | None = None

    @classmethod
    def error_result(cls, error: str, output: str = "", **kwargs: Any):
        return cls(
            success=False,
            output=output,
            error=error,
            **kwargs,
        )

    @classmethod
    def success_result(
        cls,
        output: str,
        metadata: dict[str, Any] = {},
        truncated: bool = False,
        diff: FileDiff | None = None,
    ):
        return cls(
            success=True,
            output=output,
            metadata=metadata,
            truncated=truncated,
            diff=diff,
        )

    def to_model_output(self) -> str:
        """If the ToolResult is succesful, returns the output of the tool, otherwise it returns
        an error. This is such that the model knows what the tool execution has done."""
        if self.success:
            return self.output

        return f"Error: {self.error}\n\nOutput:\n{self.output}"


class Tool(abc.ABC):
    name: str = "base_tool"
    # Helps the LLM choose the right tools
    description: str = "Base tool"
    kind: ToolKind = ToolKind.READ

    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def schema(self) -> dict[str, Any] | type[BaseModel]:
        """Schema returning a type dict compatible with MCP or a type inheriting BaseModel
        compatible with this pipeline"""
        raise NotImplementedError(
            "Tools must define schema property or class attribute"
        )

    @abc.abstractmethod
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        pass

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                schema(**params)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    # Get locations for this validation error
                    field = ".".join(str(x) for x in error.get("loc", []))
                    msg = error.get("msg", "Validation error")
                    errors.append(f"Parameter '{field}': {msg}")

                return errors
            except Exception as e:
                return [str(e)]
        return []

    def is_mutating(self) -> bool:
        return self.kind in [
            ToolKind.WRITE,
            ToolKind.SHELL,
            ToolKind.NETWORK,
            ToolKind.MEMORY,
        ]

    async def get_confirmation(
        self, invocation: ToolInvocation
    ) -> ToolConfirmation | None:
        if not self.is_mutating():
            return None

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.parameters,
            description=f"Execute {self.name}",
        )

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert a BaseModel class or an MCP dictionary containing the details for the tool to an
        openai supported tool schema"""
        schema = self.schema

        # Our own tool calling
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            json_schema = model_json_schema(schema, mode="serialization")

            return {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": json_schema.get("properties", {}),
                    "required": json_schema.get("required", []),
                },
            }

        # MCP handling
        if isinstance(schema, dict):
            result = {"name": self.name, "description": self.description}

            if "parameters" in schema:
                result["parameters"] = schema["parameters"]
            else:
                result["parameters"] = schema

            return result

        raise ValueError(f"Invalid schema type for tool {self.name}: {type(schema)}")
