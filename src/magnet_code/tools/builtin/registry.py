import logging
from pathlib import Path
from typing import Any
from magnet_code.tools.base import Tool, ToolInvocation, ToolResult
from magnet_code.tools.builtin import ReadFileTool, get_all_builtin_tools

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
        
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
        
    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            return True
        
        return False
    
    def get(self, name: str) -> Tool | None:
       return self._tools.get(name, None) 
    
    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = []
        
        for tool in self._tools.values():
            tools.append(tool)
        return tools
    
    def get_schemas(self) -> list[dict[str, Any]]:
        print(self.get_tools())
        return [tool.to_openai_schema() for tool in self.get_tools()]
    
    
    async def invoke(self, name: str, params: dict[str, Any], cwd: Path = None) -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult.error_result(
                f"Unknown tool: {name}",
                metadata = {"tool_name": name},
            )
            
        validation_errors = tool.validate_params(invocation.params)
        if validation_errors:
            return ToolResult.error_result(
                f"Invalid parameters: {'; '.join(validation_errors)}",
                metadata={"tool_name": name, "validataion_errors": validation_errors,}
            )
        
        invocation = ToolInvocation(params=params, cwd=cwd)
        
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
            
def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    
    for tool_class in get_all_builtin_tools():
        registry.register(tool_class())
    
    return registry