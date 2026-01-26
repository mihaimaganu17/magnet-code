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
        # Agent used by this CLI to process user's requests
        self.agent : Agent | None = None
        # Interface used to display agent actions, workflow and responses
        self.tui = TUI(console)
    
    async def run_single(self, message: str) -> str | None:
        """
        Run a single user message through the agent
        """
        async with Agent() as agent:
            self.agent = agent
            # Process the message and return the agent's response
            return await self._process_message(message)


    async def _process_message(self, message: str) -> str | None:
        """Function to process a single user message given to the agent"""
        # If we don't have a message, return an error
        if not self.agent:
            return None

        # Used to synchronize the response we get from the agent and the moment we display it.
        # Initially we presume that the assistant did not start streaming the respone back to us
        assistant_streaming = False
        # Holds the entire response of the LLM after the streaming is done. Initially empty
        final_response = None
        # Process each event from the agent's run
        async for event in self.agent.run(message):
            # Currently we do not have any special behaviour when we get the start event
            if event.type == AgentEventType.AGENT_START:
                pass
            elif event.type == AgentEventType.TEXT_DELTA:
                content = event.data.get("content", "")
                # Check if the assistant is currently streaming, if not
                if not assistant_streaming:
                    # Mark up on display that the assitant is responding
                    self.tui.begin_assitant()
                    assistant_streaming = True
                self.tui.stream_assistant_delta(content)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
                if assistant_streaming:
                    assistant_streaming = False
                    self.tui.end_assistant()
                    
        return final_response


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