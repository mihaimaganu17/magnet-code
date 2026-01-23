from typing import AsyncGenerator

from magnet_code.agent.events import AgentEvent


class Agent:
    def __init__(self):
        pass
    
    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Agentinc loop with multi-turn conversation
        """