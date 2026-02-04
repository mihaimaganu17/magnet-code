import os
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field


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


class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    shell_environment: ShellEnvironmentPolicy = Field(
        default_factory=ShellEnvironmentPolicy
    )
    max_turns: int = 100

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
        return self.model_dump(mode='json')