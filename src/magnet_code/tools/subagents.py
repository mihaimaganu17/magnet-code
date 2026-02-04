import asyncio
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field
from magnet_code.agent.agent import Agent
from magnet_code.agent.events import AgentEvent, AgentEventType
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
    goal_prompt: str  # similar to the system prompt
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

        # TODO: Is this to_dict conversion necessary?
        config_dict = self.config.to_dict()
        config_dict["max_turns"] = self.definition.max_turns

        if self.definition.allowed_tools:
            config_dict["allowed_tools"] = self.definition.allowed_tools

        subagent_config = Config(**config_dict)

        prompt = f"""You are a specialized sub-agent with a specific task to complete
        
        {self.definition.goal_prompt}
        
        YOUR TASK:
        {params.goal}
        
        IMPORTANT:
        - Focus only on completing the specified task
        - Do not engage in unrelated actions
        - Be factual and do not 
        - Once you have completed the task or have the answer, provide you final response
        - Do not try to cheat or make things up that are not factual in order to complete the task.
        - Be concise and direct in your output
        """
        tool_calls = []
        final_response = None
        error = None
        # By default we assume the subagent terminated because it achieved the desired goal
        terminate_response = "goal"

        try:
            async with Agent(subagent_config) as agent:
                deadline = (
                    asyncio.get_event_loop().time() + self.definition.timeout_seconds
                )
                async for event in agent.run(prompt):
                    if asyncio.get_event_loop().time() > deadline:
                        terminate_response = "timeout"
                        final_response = "Subagent timed out"
                        break

                    if event.type == AgentEventType.TOOL_CALL_START:
                        tool_calls.append(event.data.get("name"))
                    elif event.type == AgentEventType.TEXT_COMPLETE:
                        final_response = event.data.get("content")
                    elif event.type == AgentEventType.AGENT_ERROR:
                        error = event.data.get("error", "Unknown")
                        final_response = f"Subagent error: {error}"
                        terminate_response = "error"
                        break
        except Exception as e:
            terminate_response = "error"
            error = str(e)
            final_response = f"subagent failed: {e}"

        result = f"""Subagent `{self.definition.name}` completed.
        Termination: {terminate_response}
        Tools called: {', '.join(tool_calls) if tool_calls else 'None'}
        
        Result:
        {final_response or 'No response'}
        """

        if error:
            return ToolResult.error_result(result)

        return ToolResult.success_result(result)


CODEBASE_INVESTIGATOR = SubagentDefinition(
    name="codebase_investigator",
    description="Invetigates the codebase to answer questions about code structure",
    goal_prompt="""You are a codebase investigation specialist. You job is to explore and understand
    code to answer questions. Use read_file, grep, glob, and list_dir to investigate. Do NOT modify
    any files.
    """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
    max_turns=15,
)

CODE_REVIEWER = SubagentDefinition(
    name="code_reviewer",
    description="Reviews code changes and provides feedback on quality, bugs and improvements",
    goal_prompt="""You are a code review specialist. Your job is to review code and provide
    constructive feedback. Look for bugs, code smells, security issues, and improvement opportunities.
    Use read_file, list_dir and grep to examine the code. Do NOT modify any files.
    """,
    allowed_tools=["read_file", "grep", "glob", "list_dir"],
    max_turns=15,
)
