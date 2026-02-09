import asyncio
from magnet_code.config.config import Config
from magnet_code.tools.builtin.registry import ToolRegistry
from magnet_code.tools.mcp.client import MCPClient, MCPServerStatus
from magnet_code.tools.mcp.tool import MCPTool


class MCPManager:
    def __init__(self, config: Config):
        self.config = config
        self._clients: dict[str, MCPClient] = {}
        self._initialized = False
        
    async def initialize(self) -> None:
        if self._initialized:
            return
        
        mcp_configs = self.config.mcp_servers
        
        if not mcp_configs:
            return
        
        for name, server_config in mcp_configs.items():
            if not server_config.enabled:
                continue
            
            self._clients[name] = MCPClient(
                name=name,
                config=server_config,
                cwd=self.config.cwd,
            )
            
        connection_tasks = [asyncio.wait_for(client.connect(), timeout=client.config.startup_timeout_sec) for _name, client in self._clients.items()]

        await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        self._initialized = True


    def register_tools(self, registry: ToolRegistry) -> int:
        count = 0
        
        for client in self._clients.values():
            # Only register tools from a connected MCP server
            if client.status != MCPServerStatus.CONNECTED:
                continue
            
            for tool_info in client.tools:
                mcp_tool = MCPTool(
                   tool_info=tool_info,
                   client=client,
                   config=self.config,
                   name=f"{client.name}__{tool_info.name}",
                )
                registry.register_mcp_tool(mcp_tool)
                count += 1
        
        return count