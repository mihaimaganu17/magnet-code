from typing import AsyncGenerator

from magnet_code.agent.events import AgentEvent
from magnet_code.client.llm_client import LLMClient
from magnet_code.client.response import EventType, StreamEventType


class Agent:
    def __init__(self):
        # Create a new client for this agent
        self.client = LLMClient()

    async def run(self, message: str):
        # Communicate back that the agent has started
        yield AgentEvent.agent_start(message)
        

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Agentic loop with:
        - multi-turn conversation
        - context management (coming soon)
        """
        messages = [{"role": "user", "content": "What's up"}]
        async for event in self.client.chat_completion(messages, True):
            # If the stream event is a text delta
            if event.type == StreamEventType.TEXT_DELTA:
                # We convert it to the delta agent event
                content = event.text_delta.content
                yield AgentEvent.text_delta(content)
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown error occurred.")
