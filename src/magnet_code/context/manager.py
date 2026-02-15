from datetime import datetime
from typing import Any
from magnet_code.client.response import TokenUsage
from magnet_code.config.config import Config
from magnet_code.prompts.system import get_system_prompt
from dataclasses import dataclass, field

from magnet_code.tools.base import Tool
from magnet_code.utils.text import count_tokens


@dataclass
class MessageItem:
    role: str
    content: str
    token_count: int | None = None
    # Why do we have a single tool call if there are many tool calls?
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    pruned_at: datetime | None = None

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
    # Keep the last 40_000 tokens of the most recent tool outputs
    PRUNE_PROTECT_TOKENS = 40_000
    # If we can free at least this amount of tokens, we prune
    PRUNE_MINIMUM_TOKENS = 20_000
    
    def __init__(self, config: Config, user_memory: str | None, tools: list[Tool] | None) -> None:
        self.config = config
        self._model_name = config.model_name
        self._system_prompt = get_system_prompt(self.config, user_memory, tools)
        self._messages: list[MessageItem] = []
        self._latest_usage = TokenUsage()
        self._total_usage = TokenUsage()

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def total_usage(self) -> TokenUsage:
        return self._total_usage

    @total_usage.setter
    def total_usage(self, total_usage: TokenUsage):
        self._total_usage = total_usage

    def add_user_message(self, content: str) -> None:
        item = MessageItem(
            role="user",
            content=content or "",
            token_count=count_tokens(content, self._model_name),
        )
        self._messages.append(item)

    def add_assistant_message(self, content: str, tool_calls: list[dict[str, Any]]) -> None:
        item = MessageItem(
            role="assistant",
            content=content or "",
            token_count=count_tokens(content, self._model_name),
            tool_calls=tool_calls or [],
        )
        self._messages.append(item)

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        item = MessageItem(
            role='tool',
            content=content,
            tool_call_id=tool_call_id,
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

    def needs_compression(self) -> bool:
        context_limit = self.config.model.context_window
        current_token = self._latest_usage.total_tokens

        print(context_limit)
        print(current_token)
        return current_token > context_limit * 0.8


    def set_latest_usage(self, usage: TokenUsage):
        self._latest_usage = usage

    def add_usage(self, usage: TokenUsage):
        self._total_usage += usage

    def replace_with_summary(self, summary: str) -> None:
        self._messages = []

        continuation_content = f"""# Context Restoration (Previous Session Compacted)

        The previous conversation was compacted due to context length limits. Below is a detailed summary of the work done so far. 

        **CRITICAL: Actions listed under "COMPLETED ACTIONS" are already done. DO NOT repeat them.**

        ---

        {summary}

        ---

        Resume work from where we left off. Focus ONLY on the remaining and in progress tasks."""

        summary_item = MessageItem(
            role='user',
            content=continuation_content,
            token_count=count_tokens(continuation_content, self._model_name),
        )
        self._messages.append(summary_item)

        # Add an acknowledgment message (fabricated as assistant) to reenforce for the assistant
        # the idea that we have summarized the context.
        # We are essentially gaslighting the llm
        ack_content = """I've reviewed the context from the previous session. I understand:
- The original goal and what was requested
- Which actions are ALREADY COMPLETED (I will NOT repeat these)
- The current state of the project
- What still needs to be done

I'll continue with the REMAINING tasks only, starting from where we left off."""

        ack_item = MessageItem(
            role='assistant',
            content=ack_content,
            token_count=count_tokens(ack_content, self._model_name),
        )

        self._messages.append(ack_item)

        # We cannot end with an assistant message, so we add another user reinforcing message
        continue_content = (
            "Continue with the REMAINING work only. Do NOT repeat any completed actions. "
            "Proceed with the next step as described in the context above."
        )

        continue_item = MessageItem(
            role="user",
            content=continue_content,
            token_count=count_tokens(continue_content, self._model_name),
        )
        self._messages.append(continue_item)

    def prune_tool_outputs(self) -> int:
        """Prune the tool outputs and return the number of tokens pruned"""

        # Count the number of user messages
        user_message_count = sum(1 for msg in self._messages if msg.role == "user")

        if user_message_count < 2:
            return 0

        # Number of total tokens
        total_tokens = 0
        # Number of tokens we are pruning
        pruned_tokens = 0
        to_prune: list[MessageItem] = []
        # From the latest tool messages up to the initial
        for msg in reversed(self._messages):
            # Tool results are more expensive token wise than tool calls and we want to prune those
            if msg.role == 'tool' and msg.tool_call_id:
                # We already hit the last message that was pruned
                if msg.pruned_at:
                    break
                tokens = msg.token_count or count_tokens(msg.content, self._model_name)
                total_tokens += tokens

                if total_tokens > self.PRUNE_PROTECT_TOKENS:
                    pruned_tokens += tokens
                    to_prune.append(msg)

        if pruned_tokens < self.PRUNE_MINIMUM_TOKENS:
            return 0

        # number of messages we pruned
        pruned_count = 0

        for msg in to_prune:
            msg.content = '[Old tool result content cleared]'
            msg.token_count = count_tokens(msg.content, self._model_name)
            msg.pruned_at = datetime.now()
            pruned_count += 1

        return pruned_count

    def clear(self) -> None:
        self._messages = []
