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
)


class LLMClient:
    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        # How many times we should retry if a request to the client fails
        self._max_retries: int = 3

    def get_client(self) -> AsyncOpenAI:
        # If client is not created, create a new client
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("OPENAI_API_URL"),
            )
        return self._client

    async def close(self) -> None:
        """Close the client"""
        if self._client:
            await self._client.close()
            self._client = None

    def _build_tools(self, tools: list[dict[str, Any]]):
        """Encapsulate each tool in a function type"""
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
        model = "gpt-5.2"
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
        of the streaming response, yielding a new text `StreamEvent` for each LLM token response
        and issue a final message complete event. Also gather usage information if present
        """
        # Make a chat completion request with the desired client and configuration
        response = await client.chat.completions.create(**kwargs)

        # Why the LLM stopped generating the response further
        finish_reason: str | None = None
        # The token usage for this request
        usage: TokenUsage | None = None

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
            # Check if this chunk has any response choices. If not, go to the next chunk
            if not chunk.choices:
                continue

            # Get the first choice from the chunk and its text content located in `delta`
            choice = chunk.choices[0]
            text_delta = choice.delta

            # If we get a finish reason, we update it locally
            if choice.finish_reason:
                finish_reason = choice.finish_reason

            # If the text delta has content, issue a `StreamEvent` of text delta progress. This is
            # usually another token that the LLM has generated.
            if text_delta.content:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(content=text_delta.content),
                    finish_reason=finish_reason,
                    usage=usage,
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
