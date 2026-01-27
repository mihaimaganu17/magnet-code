from typing import Any
from magnet_code.prompts.system import get_system_prompt
from dataclasses import dataclass

from magnet_code.utils.text import count_tokens


@dataclass
class MessageItem:
    role: str
    content: str
    token_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Converts `self` to a dict compatible with OpenAI API spec for messages"""
        result: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        return result


class ContextManager:
    def __init__(self) -> None:
        self._model_name = "gpt-o1"
        self._system_prompt = get_system_prompt()
        self._messages: list[MessageItem] = []

    def add_user_message(self, content: str) -> None:
        item = MessageItem(
            role="user",
            content=content or "",
            token_count=count_tokens(content, self._model_name),
        )
        self._messages.append(item)

    def add_assistant_message(self, content: str) -> None:
        item = MessageItem(
            role="assitant",
            content=content or "",
            token_count=count_tokens(content, self._model_name),
        )
        self._messages.append(item)


    def get_messages(self) -> list[dict[str, Any]]:
        """Convert the message into the OpenAI format, which is a list of dicitionaries where each
        dictionary has a `role` and a `content` key"""
        messages = []
        if self._system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": self._system_prompt,
                }
            )

        for item in self._messages:
            messages.append(item.to_dict())
            
        return messages
