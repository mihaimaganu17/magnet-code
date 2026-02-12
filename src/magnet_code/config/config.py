from __future__ import annotations
from enum import Enum
import fnmatch
import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, model_validator


class ModelConfig(BaseModel):
    name: str = "gpt-5.2"
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    context_window: int = 400_000


class ShellEnvironmentPolicy(BaseModel):
    ignore_default_excludes: bool = False
    exclude_patterns: list[str] = Field(
        default_factory=lambda: ["*KEY*", "*TOKEN", "*SECRET*", "*SECURITY*"]
    )
    # Overriding variables
    set_vars: dict[str, str] = Field(default_factory=dict)

    def _build_environment(self) -> dict[str, str]:
        env = os.environ.copy()

        if not self.ignore_default_excludes:
            for pattern in self.exclude_patterns:
                # Match and compile a list of all the environment variables against the pattern
                keys_to_remove = [
                    k for k in env.keys() if fnmatch.fnmatch(k.upper(), pattern.upper())
                ]
                for k in keys_to_remove:
                    del env[k]

        # Check if we need to update any override keys
        if self.set_vars:
            env.update(self.set_vars)

        return env


class MCPServerConfig(BaseModel):
    enabled: bool = True
    # How much time should we wait for this MCP to load
    startup_timeout_sec: float = 10

    # stdio transport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path | None = None

    # http/sse transport
    url: str | None = None

    @model_validator(mode="after")
    def validate_transport(self) -> MCPServerConfig:
        has_command = self.command is not None
        has_url = self.url is not None

        if not has_command and not has_url:
            raise ValueError(
                "MCP Server must have either 'command' (stdio) or 'url' (http/sse)"
            )

        if has_command and has_url:
            raise ValueError(
                "MCP Server cannot have both 'command' (stdio) and 'url' (http/sse)"
            )

        return self


class ApprovalPolicy(str, Enum):
    ON_REQUEST = "on-request"
    ON_FAILURE = "on-failure"
    AUTO = "auto"
    AUTO_EDIT = "auto-edit"
    NEVER = "never"
    YOLO = "yolo"

class HookTrigger(str, Enum):
    BEFORE_AGENT = 'before_agent'
    AFTER_AGENT = 'after_agent'
    BEFORE_TOOL = 'before_tool'
    AFTER_TOOL = 'after_tool'
    ON_ERROR = 'on_error'

class HookConfig(BaseModel):
    name: str
    trigger: HookTrigger
    command: str | None = None
    script: str | None = None # .sh shell script
    timeout_sec: float = 30
    enabled: bool = True

    @model_validator(mode='after')
    def validate_hook(self) -> HookConfig:
        if not self.command and not self.script:
            raise ValueError("Hook must either have 'command' or script")
        return self


class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    shell_environment: ShellEnvironmentPolicy = Field(
        default_factory=ShellEnvironmentPolicy
    )
    hooks_enabled: bool = False
    hooks: list[HookConfig] = Field(default_factory=HookConfig)
    approval: ApprovalPolicy = ApprovalPolicy.ON_REQUEST
    max_turns: int = 100
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)

    allowed_tools: list[str] | None = Field(
        None, description="If set, only these tools will be available for the agent"
    )

    max_tool_output_tokens: int = 50_000

    developer_instructions: str | None = None
    user_instructions: str | None = None

    debug: bool = False

    @property
    def api_key(self) -> str | None:
        return os.environ.get("OPENAI_API_KEY")

    @property
    def base_url(self) -> str | None:
        return os.environ.get("BASE_URL")

    @property
    def model_name(self) -> str:
        return self.model.name

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value

    @property
    def temperature(self) -> float:
        return self.model.temparature

    @model_name.setter
    def temperature(self, value: float) -> None:
        self.model.temparature = value

    def validate(self) -> list[str]:
        """Validates if essential options like API_KEY and working directory are present in the
        configuration."""
        errors: list[str] = []

        if not self.api_key:
            errors.append("No API key found. Set OPENAI_API_KEY environemnt variable")

        if not self.cwd.exists():
            errors.append(f"Working directory does not exist: {self.cwd}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
