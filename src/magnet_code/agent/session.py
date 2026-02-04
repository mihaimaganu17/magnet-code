import datetime
import json
import uuid
from magnet_code.client.llm_client import LLMClient
from magnet_code.config.config import Config
from magnet_code.config.loader import get_data_dir
from magnet_code.context.manager import ContextManager
from magnet_code.tools.builtin.registry import create_default_registry


class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)
        self.tool_registry = create_default_registry(config)
        self.context_manager = ContextManager(
            config,
            user_memory=self._load_memory(),
            tools=self.tool_registry.get_tools(),
        )
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.datetime.now()
        self.updated_at = datetime.datetime.now()

        # How many turns have been taking place in the session
        self._turn_count = 0

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
