from typing import Any
from openai import AsyncOpenAI

import os

class LLMClient:
    def __init__(self) -> None:
        self._client : AsyncOpenAI | None = None

    def get_client(self) -> AsyncOpenAI:
        # If client is not created, create a new client
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=os.environ.get('OPENAI_API_KEY'),
                base_url=os.environ.get('OPENAI_API_URL'),
            )
        return self._client
            
    async def close(self) -> None:
        """Close the client"""
        if self._client:
            await self._client.close()
            self._client = None

    async def chat_completion(self, messages: list[dict[str, Any]], stream: bool = True):
        if stream:
            self._stream_response()
        else:
            self._non_stream_response()

    async def _stream_response(self):
        pass

    async def _non_stream_response(self):
        pass