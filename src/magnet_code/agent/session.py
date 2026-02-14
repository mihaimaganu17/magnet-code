import datetime
import json
from typing import Any
import uuid
from magnet_code.client.llm_client import LLMClient
from magnet_code.config.config import Config
from magnet_code.config.loader import get_data_dir
from magnet_code.config.loop_detector import LoopDetector
from magnet_code.context.compaction import ChatCompactor
from magnet_code.context.manager import ContextManager
from magnet_code.hooks.hook_system import HookSystem
from magnet_code.safety.approval import ApprovalManager
from magnet_code.tools.builtin.registry import create_default_registry
from magnet_code.tools.discovery import ToolDiscoveryManager
from magnet_code.tools.mcp.manager import MCPManager


class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)
        self.tool_registry = create_default_registry(config)
        self.context_manager: ContextManager | None = None

        self.discovery_manager = ToolDiscoveryManager(config, self.tool_registry)
        self.mcp_manager = MCPManager(self.config)
        self.chat_compactor = ChatCompactor(self.client)
        self.approval_manager = ApprovalManager(self.config.approval, self.config.cwd,)
        self.loop_detector = LoopDetector()
        self.hook_system = HookSystem(config)
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.datetime.now()
        self.updated_at = datetime.datetime.now()


        # How many turns have been taking place in the session
        self._turn_count = 0

    
    async def initialize(self) -> None:
        await self.mcp_manager.initialize()
        self.mcp_manager.register_tools(self.tool_registry)
        self.discovery_manager.discover_all()

        self.context_manager =  ContextManager(
            config=self.config,
            user_memory=self._load_memory(),
            tools=self.tool_registry.get_tools(),
        )
 

    def _load_memory(self) -> str | None:
        data_dir = get_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        path = data_dir / "user_memory.json"

        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            entries = data.get("entries")
            if not entries:
                return None
            lines = ["User preferencec and notes:"]
            for key, value in entries.items():
                lines.append(f"- {key}: {value}")
            return "\n".join(lines)
        except Exception:
            return None

    def increment_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.datetime.now()

        return self._turn_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            'turn_count': self._turn_count,
            "message_count": self.context_manager.message_count,
            "token_usage": self.context_manager.total_usage,
            "tools_count": len(self.tool_registry.get_tools()),
            "mcp_servers": len(self.tool_registry.connected_mcp_servers),
        }
