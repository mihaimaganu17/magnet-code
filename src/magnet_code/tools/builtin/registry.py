import logging
from pathlib import Path
from typing import Any
from magnet_code.config.config import Config
from magnet_code.tools.base import Tool, ToolInvocation, ToolResult
from magnet_code.tools.builtin import ReadFileTool, get_all_builtin_tools
from magnet_code.tools.subagents import SubAgentTool, get_default_subagent_defintions

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self, config: Config):
        self._tools: dict[str, Tool] = {}
        self._mcp_tools: dict[str, Tool] = {}
        self.config = config
        
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def register_mcp_tool(self, tool: Tool) -> None:
        self._mcp_tools[tool.name] = tool 
        logger.debug(f"Registered MCP tool: {tool.name}")
        
    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        
        return False
    
    def get(self, name: str) -> Tool | None:
       if name in self._tools:
           return self._tools[name]
       elif name in self._mcp_tools:
           return self._mcp_tools[name]
       return None
    
    def get_tools(self) -> list[Tool]:
        """Get a list of all the available tools in this registry"""
        tools: list[Tool] = []
        
        for tool in self._tools.values():
            tools.append(tool)

        for mcp_tool in self._mcp_tools.values():
            tools.append(mcp_tool)

        # Filter allowed tools
        if self.config.allowed_tools:
            allowed_set = set(self.config.allowed_tools)
            tools = [t for t in tools if t.name in allowed_set]

        return tools
    
    def get_schemas(self) -> list[dict[str, Any]]:
        """Convert the list of tools into an OpenAI API compatible tool schema in order to be
        added to the LLM request such that the LLM knows which are the available tools"""
        return [tool.to_openai_schema() for tool in self.get_tools()] 
    
    async def invoke(self, name: str, params: dict[str, Any], cwd: Path = None) -> ToolResult:
        """Invoke a tool identified by `name` with the desired `params` in the desired working
        directory. If the name does not identify a tool in the current registry or the parameters
        are not valid for the desired tool or the tool execution fails, an error `ToolResult` is
        issued."""
        
        # Get the tool by name and check its existence
        tool = self.get(name)
        if tool is None:
            return ToolResult.error_result(
                f"Unknown tool: {name}",
                metadata = {"tool_name": name},
            )
            
        # Validate that the parameters given from the LLM, match the model tool schema
        validation_errors = tool.validate_params(params)
        # If there are any validation errors, we return them
        if validation_errors:
            return ToolResult.error_result(
                f"Invalid parameters: {'; '.join(validation_errors)}",
                metadata={"tool_name": name, "validataion_errors": validation_errors,}
            )
        
        # Wrapper type, easy to use
        invocation = ToolInvocation(parameters=params, cwd=cwd)
        
        try:
            result = await tool.execute(invocation)
            return result
        except Exception as e:
            logger.exception(f"Tool {tool.name} raised unexpected error")
            return ToolResult.error_result(
                f"Internal error: {str(e)}",
                metadata={
                    "tool_name": name,
                }
            )
            
def create_default_registry(config: Config) -> ToolRegistry:
    """Create a default registry which has all the builtin tools"""
    registry = ToolRegistry(config)
    
    for tool_class in get_all_builtin_tools():
        registry.register(tool_class(config))
        
    for subagent_def in get_default_subagent_defintions():
        registry.register(SubAgentTool(config, subagent_def))
    
    return registry