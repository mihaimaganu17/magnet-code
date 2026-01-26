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
        final_response: str | None = None
        # Process each event from the agent's run
        async for event in self.agent.run(message):
            # Currently we do not have any special behaviour when we get the start event
            if event.type == AgentEventType.AGENT_START:
                pass
            # If we have a text delta for generation progress
            elif event.type == AgentEventType.TEXT_DELTA:
                # We get the content from the event
                content = event.data.get("content", "")
                # If the assistant is currently marked as NOT streaming a response
                if not assistant_streaming:
                    # Mark up on display that the assitant is starting to respond
                    self.tui.begin_assitant()
                    # Update the local state
                    assistant_streaming = True
                # Print the content we got on the TUI
                self.tui.stream_assistant_delta(content)
            # If we get a text completion event (response finished generation)
            elif event.type == AgentEventType.TEXT_COMPLETE:
                # Get the final response to be returned
                final_response = event.data.get("content")
                # If the assistant is currently marked as streaming a response
                if assistant_streaming:
                    # Mark it as not streaming, because it finished
                    assistant_streaming = False
                    # Mark the same state for the TUI
                    self.tui.end_assistant()
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                console.print(f"\n[error]Error: {error}[/error]")
                
        # Return the final response gathered by the agent            
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