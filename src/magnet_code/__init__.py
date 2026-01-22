import asyncio
from magnet_code.client.llm_client import LLMClient


def hello() -> str:
    return "Hello from magnet-code!"


async def main():
    client = LLMClient()
    messages = [
        {
            "role": "user",
            "content": "What's up"
        }
    ]
    async for event in client.chat_completion(messages, False):
        print(event)

asyncio.run(main())