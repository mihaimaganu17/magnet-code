from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from magnet_code.agent.agent import Agent
from magnet_code.config.config import Config
from magnet_code.tools.base import Tool, ToolInvocation, ToolResult
from pydantic import BaseModel


class SubagentParams(BaseModel):
    goal: str = Field(
        ..., description="The specific taks or goal for the subagent to accomplish"
    )


@dataclass
class SubagentDefinition:
    name: str  # subagent_name
    description: str
    goal_prompt: str
    allowed_tools: list[str] | None = None
    max_turns: int = 20
    timeout_seconds: float = 600


class SubAgentTool(Tool):
    schema = SubagentParams

    def __init__(self, config: Config, definition: SubagentDefinition):
        super().__init__(config)
        self.definition = definition

    @property
    def name(self) -> str:
        return f"subagent_{self.definition.name}"

    @property
    def description(self) -> str:
        return f"subagent {self.definition.description}"

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return True

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = SubagentParams(**invocation.parameters)

        if not params.goal:
            return ToolResult.error_result("No goal specified for subagent")

        try:
            async with Agent(self.config)
        except Exception as e:
            ...