from typing import Any
from magnet_code.prompts.system import get_system_prompt
from dataclasses import dataclass, field

from magnet_code.utils.text import count_tokens


@dataclass
class MessageItem:
    role: str
    content: str
    token_count: int | None = None
    # Why do we have a single tool call if there are many tool calls?
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factor=list)

    def to_dict(self) -> dict[str, Any]:
        """Converts `self` to a dict compatible with OpenAI API spec for messages"""
        result: dict[str, Any] = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_call_id:
            result['tool_call_id'] = self.tool_call_id
        if self.tool_calls:
            result['tool_calls'] = self.tool_calls
            
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

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        item = MessageItem(
            role='tool',
            content=content,
            tool_call_id=tool_call_id
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
