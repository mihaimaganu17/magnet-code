import asyncio
import sys
from typing import Any
from magnet_code.agent.agent import Agent
from magnet_code.agent.events import AgentEventType
from magnet_code.client.llm_client import LLMClient


import click

from magnet_code.ui.tui import TUI, get_console

console = get_console()

class CLI:
    def __init__(self):
        self.agent : Agent | None = None
        self.tui = TUI(console)
    
    async def run_single(self, message: str) -> str | None:
        async with Agent() as agent:
            self.agent = agent
            return await self._process_message(message)

    async def _process_message(self, message: str) -> str | None:
        # If we don't have a message, return an error
        if not self.agent:
            return None

        # Process each event from runnning
        async for event in self.agent.run(message):
            if event.type == AgentEventType.AGENT_START:
                pass
            elif event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                self.tui.stream_assistant_delta(content)


@click.command()
@click.argument("prompt", required=False)
def main(
    prompt: str | None,
):
    # Create a new CLI
    cli = CLI()
    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]
    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)

main()