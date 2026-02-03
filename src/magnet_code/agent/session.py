import datetime
import uuid
from magnet_code.client.llm_client import LLMClient
from magnet_code.config.config import Config
from magnet_code.context.manager import ContextManager
from magnet_code.tools.builtin.registry import create_default_registry


class Session:
    def __init__(self, config: Config):
        self.config = config
        self.client = LLMClient(config)
        self.context_manager = ContextManager(config)
        self.tool_registry = create_default_registry(self.config)
        self.session_id = str(uuid.uuid4())
        self.created_at = datetime.datetime.now()
        self.updated_at = datetime.datetime.now()
        
        # How many turns have been taking place in the session
        self._turn_count = 0
        
    
    def increment_turn(self) -> int:
        self._turn_count += 1
        self.updated_at = datetime.datetime.now()
        
        return self._turn_count