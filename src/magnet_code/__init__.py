import asyncio
from magnet_code.client.llm_client import LLMClient


import click

@click.command()
@click.argument("prompt", required=False)
async def main():
    client = LLMClient()
    messages = [
        {
            "role": "user",
            "content": "What's up"
        }
    ]
    async for event in client.chat_completion(messages, True):
        print(event)

asyncio.run(main())

if __name__ == '__main__':