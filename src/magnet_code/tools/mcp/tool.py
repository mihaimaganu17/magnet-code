from typing import Any
from magnet_code.config.config import Config
from magnet_code.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from magnet_code.tools.mcp.client import MCPClient, MCPToolInfo
from magnet_code.utils.paths import resolve_path


class MCPTool(Tool):
    def __init__(
        self, config: Config, client: MCPClient, tool_info: MCPToolInfo, name: str
    ) -> None:
        super().__init__(config)
        self._tool_info = tool_info
        self._client = client
        self.name = name
        self.description = self._tool_info.description
        
    @property
    def schema(self) -> dict[str, Any]:
        input_schema = self._tool_info.input_schema or {}
        return {
            "type": "object",
            "properties": input_schema.get("properties", {}),
            "required": input_schema.get("required", []),
        }    

    def is_mutating(self, params) -> bool:
        return True

    kind = ToolKind.MCP

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        try:
            result = await self._client.call_tool(self._tool_name.name, invocation.parameters)
            output = result.get("output", "")
            is_error = result.get("is_error", False)

            if is_error:
                return ToolResult.error_result(output)

            return ToolResult.success_result(output)
        except Exception:
            return ToolResult.error_result(f"MCP tool failed: {e}")