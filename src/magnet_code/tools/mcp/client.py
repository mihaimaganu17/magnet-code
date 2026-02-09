from enum import Enum
import os
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport, SSETransport
from magnet_code.config.config import MCPServerConfig, ShellEnvironmentPolicy

class MCPServerStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class MCPClient:
    def __init__(self, name: str, config: MCPServerConfig, cwd: Path):
        self.name = name
        self.config = config
        self.cwd = cwd
        self.status = MCPServerStatus.DISCONNECTED
        self._client: Client | None = None
        
    def _create_transport(self) -> StdioTransport | SSETransport:
        if self.config.command:
            env = ShellEnvironmentPolicy(**{"ignore_default_excludes": True})._build_environment()
            print(env)
            
            return StdioTransport(
                command=self.config.command,
                args=list(self.config.args),
                env=env,
            )
        
 
    async def connect(self) -> None:
        if self.status == MCPServerStatus.CONNECTED:
            return
        
        self.status = MCPServerStatus.CONNECTING
        
        self._client = Client
        