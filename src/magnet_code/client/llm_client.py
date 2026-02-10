import asyncio
from typing import Any, AsyncGenerator
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

import os

import tiktoken

from magnet_code.client.response import (
    StreamEventType,
    StreamEvent,
    TextDelta,
    TokenUsage,
    ToolCall,
    ToolCallDelta,
    parse_tool_call_arguments,
)
from magnet_code.config.config import Config


class LLMClient:
    def __init__(self, config: Config) -> None:
        self._client: AsyncOpenAI | None = None
        # How many times we should retry if a request to the client fails
        self._max_retries: int = 3
        self.config = config

    def get_client(self) -> AsyncOpenAI:
        # If client is not created, create a new client
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
        return self._client

    async def close(self) -> None:
        """Close the client"""
        if self._client:
            await self._client.close()
            self._client = None

    def _build_tools(self, tools: list[dict[str, Any]]):
        """Encapsulate each tool in a function type to match the OpenAI API model"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "parameters",
                        {
                            "type": "object",
                            "properties": {},
                        },
                    ),
                },
            }
            for tool in tools
        ]

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = True,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Handles a streaming or non-streaming chat completion request to the LLM"""
        # Get a handle to the client
        client = self.get_client()

        # TODO: Temporary hard coded value for the model, which will be replaced by a configurable
        # setting
        model = self.config.model_name
        # Arguments to handel configuration, content and options for the LLM request
        kwargs = {"model": model, "messages": messages, "stream": stream}

        if tools:
            kwargs["tools"] = self._build_tools(tools)
            kwargs["tool_choice"] = "auto"

        # Manages error handling and retries in case the request fails
        for attempt in range(self._max_retries + 1):
            try:
                # If we have a streaming request
                if stream:
                    # Handle the streaming events from the LLMs response
                    async for event in self._stream_response(client, kwargs):
                        # TODO: When streaming the response, openai api does not return the usage,
                        # so we need to compute it ourselves.
                        if event.type == StreamEventType.MESSAGE_COPLETE:
                            pass
                            # prompt_tokens = len(tiktoken.encoding_for_model(model))
                            # event.usage.prompt_tokens = prompt_tokens
                        yield event
                # Otherwise handle the non-streaming response
                else:
                    event = await self._non_stream_response(client, kwargs)
                    yield event
                # At this point, we have successfully yielded all the events and we can return
                return
            # Check if the request exceeds some rate limit
            except RateLimitError as e:
                # If we still have at least one try
                if attempt < self._max_retries:
                    # Implement exponential backoff (each time we double the wait time)
                    wait_time = 2**attempt
                    # Sleep for the desired time
                    await asyncio.sleep(wait_time)
                # If we have no other attempt, return an error
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Rate limit exceeded: {e}",
                    )
            # Check if there is a connection error
            except APIConnectionError as e:
                # If we still have at least one try
                if attempt < self._max_retries:
                    # Implement exponential backoff (each time we double the wait time)
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Connection error: {e}",
                    )
            # Check if the API returned an error
            except APIError as e:
                yield StreamEvent(
                    type=StreamEventType.ERROR,
                    error=f"API error: {e}",
                )
        # At this point, we have exceeded and failed all the attempts to get a response
        return

    async def _stream_response(
        self, client: AsyncOpenAI, kwargs: dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Perform a chat completion request with the desired configuration. Handle the progress
        of the streaming response, yielding a new `StreamEvent` for each LLM streamed response
        and issue a final text message complete event. Also gather usage information if present
        """
        # Make a chat completion request with the desired client and configuration
        response = await client.chat.completions.create(**kwargs)

        # Why the LLM stopped generating the response further
        finish_reason: str | None = None
        # The token usage for this request
        usage: TokenUsage | None = None
        # The tool calls that the LLM gave as a response
        tool_calls: dict[int, dict[str, Any]] = {}

        # For each response chunk
        async for chunk in response:
            # The usage attribute is only present in the last chunks, so we have to check for it
            if hasattr(chunk, "usage") and chunk.usage:
                # Gather the usage
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )
            else:
                # Generating fake content to use as usage
                usage = TokenUsage(
                    prompt_tokens=100,
                    completion_tokens=500,
                    total_tokens=700,
                    cached_tokens=2000,
                )
            # Check if this chunk has any response choices. If not, go to the next chunk
            if not chunk.choices:
                continue

            # Get the first choice from the chunk and its text content located in `delta`
            choice = chunk.choices[0]
            delta = choice.delta

            # If we get a finish reason, we update it locally
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            # If the delta response has content, issue a `StreamEvent` of text delta progress. This is
            # usually another token that the LLM has generated.
            if delta.content:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(content=delta.content),
                    finish_reason=finish_reason,
                    usage=usage,
                )
                
            # If the delta response has tool calls, because they are streaming, we need to gather
            # them in a single `tool_calls` list and construct their parameters
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    # Get the index of the tool call
                    idx = tool_call_delta.index

                    # If the idx of the tool call is not already mapped, create a new mapping for it
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            'id': tool_call_delta.id or "",
                            'name': '',
                            'arguments': ''
                        }
                        
                    # If we have a function field and the we are keeping track of the index in `tool_calls`
                    if tool_call_delta.function and idx in tool_calls:
                        # Get the function name and assign it in the `tool_calls`
                        if tool_call_delta.function.name:
                            tool_calls[idx]['name'] = tool_call_delta.function.name
                            # Return an event for the agent to tell it that we have a tool call
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_START,
                                tool_call_delta=ToolCallDelta(
                                    call_id=tool_calls[idx]['id'],
                                    name=tool_call_delta.function.name
                                )
                            )
                        # If we have function arguments
                        if tool_call_delta.function.arguments:
                            # Append it to the current index of arguments, as arguments are streamed
                            # just like normal text and need to be assembled
                            tool_calls[idx]['arguments'] += tool_call_delta.function.arguments
                            # Return the delta of this event  
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_DELTA,
                                tool_call_delta=ToolCallDelta(
                                    call_id=tool_calls[idx]['id'],
                                    name=tool_call_delta.function.name,
                                    arguments_delta=tool_call_delta.function.arguments
                                )
                            )

        # For each tool_call we gathered
        for idx, tc in tool_calls.items():
            # Issue an event that tells the agent we have a complete tool call which can be 
            # validated and executed
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_COMPLETE,
                tool_call=ToolCall(
                    call_id=tc['id'],
                    name=tc['name'],
                    arguments_delta=parse_tool_call_arguments(tc['arguments']),
                )
            )
        
        # Yield a final `StreamEvent` to show the completion of the response from the assistant
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COPLETE,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def _non_stream_response(
        self, client: AsyncOpenAI, kwargs: dict[str, Any]
    ) -> StreamEvent:
        """Handle a non streaming request and report the final response along with the reported
        token usage if present"""
        # Issue a chat completion request
        response = await client.chat.completions.create(**kwargs)
        # Get the first choice message
        choice = response.choices[0]
        message = choice.message

        # Get the text difference from the response
        text_delta = None
        # If the message has content, we put it in a `TextDelta` to avoid creating a new type
        if message.content:
            text_delta = TextDelta(content=message.content)
        usage = None
        
        tool_calls: list[ToolCall] = []
        # If the message contains any tool calls
        if message.tool_calls:
            # Add all the tool calls to the list
            for tc in message.tool_calls:
                tool_calls.append(
                    call_id = tc.id,
                    name=tc.function.name,
                    arguments=parse_tool_call_arguments(tc.function.arguments)
                )

        # Log token usage if any is reported
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.prompt_tokens_details.cached_tokens,
            )

        # Return a single event to show completion and the resulting response
        return StreamEvent(
            type=StreamEventType.MESSAGE_COPLETE,
            text_delta=text_delta,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
