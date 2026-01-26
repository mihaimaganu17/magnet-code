from __future__ import annotations
from typing import AsyncGenerator

from magnet_code.agent.events import AgentEvent, AgentEventType
from magnet_code.client.llm_client import LLMClient
from magnet_code.client.response import StreamEventType, StreamEventType


class Agent:
    def __init__(self):
        # Create a new LLM client for this agent that will be used to generate responses
        self.client = LLMClient()

    async def run(self, message: str):
        """Run the agent one time with the given message. The agent yields events for the start of
        the agentic loop, the end of the agentic loop and any potential error in the loop, as well
        as the text delta progress and the completion of a message."""
        # The first event in an agent's run is communicating back that the agent has started
        yield AgentEvent.agent_start(message)
        # Future add-ons:
        #   user message to context
        #   agent hooks that could run
        
        # Run the main agentic loop
        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get("content")
        
        # After the loop completed, communicate it with a final end event
        yield AgentEvent.agent_end(final_response)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        """
        Agentic loop with:
        - multi-turn conversation
        - context management (coming soon)
        """
        # Currently we use a fake messages array because we do not have context management
        messages = [{"role": "user", "content": "What's up"}]
        # Initial variable where we accumulate the response from the LLM
        response_text = ""
        
        # Issue a chat completion request to the LLM client and handle the yielded events
        async for event in self.client.chat_completion(messages, True):
            # If the stream event is a text delta (a new token generation)
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta:
                    # We convert it to the delta agent event and accumulate the content
                    content = event.text_delta.content
                    response_text += content
                    # And yield a new `AgentEvent` for content progress
                    yield AgentEvent.text_delta(content)
            # If it is an error report an agent error event as well.
            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown error occurred.")

        # After processing all events, if we have a text response, issue a `AgentEvent` to show the
        # complete text response accumulated
        if response_text:
            yield AgentEvent.text_complete(response_text)

    async def __aenter__(self) -> Agent:
        """Python helper function to open a context handler used by `with` statements"""
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Python helper function to close a context handler used by `with` statements"""
        if self.client:
            await self.client.close()
            self.client = None