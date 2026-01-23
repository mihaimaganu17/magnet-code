from typing import AsyncGenerator

from magnet_code.agent.events import AgentEvent
from magnet_code.client.llm_client import LLMClient
from magnet_code.client.response import EventType


class Agent:
    def __init__(self):
        # Create a new client for this agent
        self.client = LLMClient()

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Agentic loop with:
        - multi-turn conversation
        - context management (coming soon)
        """
        messages = [{"role": "user", "content": "What's up"}]
        async for event in self.client.chat_completion(messages, True):
            if event.type == EventType
