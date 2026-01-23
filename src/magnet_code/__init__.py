import asyncio
from typing import Any
from magnet_code.client.llm_client import LLMClient


import click

class CLI:
    def __init__(self):
        pass
    
    def run_single(self):
        pass


async def run(messages: dict[str, Any]):
    


@click.command()
@click.argument("prompt", required=False)
def main(
    prompt: str | None,
):
    print(prompt)

    messages = [
        {
            "role": "user",
            "content": "What's up"
        }
    ]
    asyncio.run(run(messages))

main()