import asyncio
from pathlib import Path
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
        self.agent: Agent | None = None
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

    async def run_interactive(self) -> str | None:
        self.tui.print_welcome(
            'Magnet',
            lines=[
                f"model: gpt-5.2",
                f"cwd: {Path.cwd()}",
                "commands: /help /config /approval /model /exit",
            ],
        )
        async with Agent() as agent:
            self.agent = agent

            while True:
                try:
                    user_input = console.input("\n[user]>[/user] ").strip()
                    if not user_input:
                        continue
                    # Process the message and return the agent's response
                    await self._process_message(user_input)
                except KeyboardInterrupt:
                    console.print("\n[dim]Use /exit to quit[/dim]")
                except EOFError:
                    break
        console.print("\n[dim]Goodbye![/dim]")

    def _get_tool_kind(self, tool_name: str) -> str | None:
        tool_kind = None
        # Get the tool from the avaible tool registry from the agent
        tool = self.agent.tool_registry.get(tool_name)

        if not tool:
            tool_kind = None
        tool_kind = tool.kind.value

        return tool_kind

    async def _process_message(self, message: str) -> str | None:
        """Function to process a single user message given to the agent.
        :return: the final response of the LLM or None if no agent is present
        :rtype: str | None"""
        # If we don't have a message, return
        if not self.agent:
            return None

        # Used to synchronize the streaming response we get from the agent and the moment we display
        # it.
        # Initially we presume that the assistant did not start streaming respones back to us
        assistant_streaming = False
        # Holds the entire response of the LLM after the streaming is done. Initially empty
        final_response: str | None = None
        # Process each event from the agent's run
        async for event in self.agent.run(message):
            # Currently we do not have any special behaviour when we get the start event
            if event.type == AgentEventType.AGENT_START:
                pass
            # If we have a text delta for LLM response generation progress
            elif event.type == AgentEventType.TEXT_DELTA:
                # We get the content from the event
                content = event.data.get("content", "")
                # If the assistant is currently marked as NOT streaming a response
                if not assistant_streaming:
                    # Mark up on display that the assitant is starting to respond
                    self.tui.begin_assitant()
                    # Update the local state such that we know the assistant is streaming on display
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
            # If we get an error, display it accordingly
            elif event.type == AgentEventType.AGENT_ERROR:
                error = event.data.get("error", "Unknown error")
                console.print(f"\n[error]Error: {error}[/error]")
            # If we have a tool call start, this means the agent wants to call a tool and we want
            # to display progress information with the tool name and the desired parameters. This
            # is useful for debugging and tool executions which need confirmation.
            elif event.type == AgentEventType.TOOL_CALL_START:
                # Get the name of the tool
                tool_name = event.data.get("name", "unknown")

                self.tui.tool_call_start(
                    event.data.get("call_id", ""),
                    tool_name,
                    self._get_tool_kind(tool_name),
                    event.data.get("arguments", {}),
                )
            elif event.type == AgentEventType.TOOL_CALL_COMPLETE:
                tool_name = event.data.get("name", "unknown")
                self.tui.tool_call_complete(
                    event.data.get("call_id", ""),
                    tool_name,
                    self._get_tool_kind(tool_name),
                    event.data.get("success", False),
                    event.data.get("output", ""),
                    event.data.get("error"),
                    event.data.get("metadata"),
                    event.data.get("truncated", False),
                )

        # Return the final response gathered by the agent
        return final_response


@click.command()
@click.argument("prompt", required=False)
def main(
    prompt: str | None,
):
    # Create a new CLI
    cli = CLI()
    messages = [{"role": "user", "content": prompt}]
    if prompt:
        result = asyncio.run(cli.run_single(prompt))
        if result is None:
            sys.exit(1)
    else:
        asyncio.run(cli.run_interactive())


main()
