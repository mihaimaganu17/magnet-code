import asyncio
from typing import Any, AsyncGenerator
from openai import APIConnectionError, AsyncOpenAI, RateLimitError

import os

import tiktoken

from magnet_code.client.response import EventType, StreamEvent, TextDelta, TokenUsage


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

    async def chat_completion(
        self, messages: list[dict[str, Any]], stream: bool = True
    ) -> AsyncGenerator[StreamEvent, None]:
        for attempt in range(self._max_retries + 1):
            try:
                client = self.get_client()
                model = "gpt-5.2"
                kwargs = {"model": model, "messages": messages, "stream": stream}
                if stream:
                    async for event in self._stream_response(client, kwargs):
                        # When streaming the response, openai api does not return the usage, so we need to
                        # compute it ourselves
                        if event.type == EventType.MESSAGE_COPLETE:
                            prompt_tokens = len(tiktoken.encoding_for_model(model))
                            event.usage.prompt_tokens = prompt_tokens
                        yield event
                else:
                    event = await self._non_stream_response(client, kwargs)
                    yield event
            # Check if the request exceeds some rate limit
            except RateLimitError as e:
                # If we still have at least one try
                if attempt < self._max_retries:
                    # Implement exponential backoff (each time we double the wait time)
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type = EventType.ERROR,
                        error = f"Rate limit exceeded: {e}",
                    )
            except APIConnectionError as e:
                # If we still have at least one try
                if attempt < self._max_retries:
                    # Implement exponential backoff (each time we double the wait time)
                    wait_time = 2**attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type = EventType.ERROR,
                        error = f"Connection error: {e}",
                    ) 
                    
        return

    async def _stream_response(
        self, client: AsyncOpenAI, kwargs: dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        response = await client.chat.completions.create(**kwargs)
        
        finish_reason: str | None = None
        usage: TokenUsage | None = None

        async for chunk in response:
            # The usage attribute is only present in the last chunks, so we have to check for it
            if hasattr(chunk, "usage") and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens,
                )
            # Check if this chunk has any choices
            if not chunk.choices:
                continue

            # Get the first choice from the chunk
            choice = chunk.choices[0]
            text_delta = choice.delta
            
            if choice.finish_reason:
                finish_reason = choice.finish_reason
                
            # If the text delta has content, issue an `StreamEvent`
            if text_delta.content:
                yield StreamEvent(
                    type = EventType.TEXT_DELTA,
                    text_delta=TextDelta(content=text_delta.content),
                    finish_reason=finish_reason,
                    usage=usage,
                )
        
        # Yield a final `StreamEvent` to show the completion of the response from the assistant
        yield StreamEvent(
            type = EventType.MESSAGE_COPLETE,
            finish_reason=finish_reason,
            usage=usage, 
        )

    async def _non_stream_response(
        self, client: AsyncOpenAI, kwargs: dict[str, Any]
    ) -> StreamEvent:
        response = await client.chat.completions.create(**kwargs)
        # Get the first choice message
        choice = response.choices[0]
        message = choice.message

        # Get the text difference from the response
        text_delta = None
        if message.content:
            text_delta = TextDelta(content=message.content)

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.prompt_tokens_details.cached_tokens,
            )

        return StreamEvent(
            type=EventType.MESSAGE_COPLETE,
            text_delta=text_delta,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
