from typing import Any, tuple
from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table

AGENT_THEME = Theme(
    {
        # General
        "info": "cyan",
        "warning": "yellow",
        "error": "bright_red bold",
        "success": "green",
        "dim": "dim",
        "muted": "grey50",
        "border": "grey35",
        "highlight": "bold cyan",
        # Roles
        "user": "bright_blue bold",
        "assistant": "bright_white",
        # Tools
        "tool": "bright_magenta bold",
        "tool.read": "cyan",
        "tool.write": "yellow",
        "tool.shell": "magenta",
        "tool.network": "bright_blue",
        "tool.memory": "green",
        "tool.mcp": "bright_cyan",
        # Code / blocks
        "code": "white",
    }
)

# Singleton console handler
_console: Console | None = None


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)

    return _console


class TUI:
    def __init__(
        self,
        console: Console | None,
    ) -> None:
        self.console = console or get_console()
        # Marks if the assistant stream should currently start building up on display
        self._assistant_stream_open = False
        self._tool_args_by_call_id: dict[str, dict[str, Any]] = {}

    def begin_assitant(self) -> None:
        """Assistant is starting to respond, so we update the internal state for that and print
        a visual indicator start"""
        self.console.print()
        self.console.print(Rule(Text("Assistant", style="assistant")))
        self._assistant_stream_open = True

    def end_assistant(self) -> None:
        if self._assistant_stream_open:
            self.console.print()
        self._assistant_stream_open = False

    def stream_assistant_delta(self, content: str) -> None:
        """Prints the streaming text delta sent from the assistant"""
        self.console.print(content, end="", markup=False)
        
    def _ordered_args(self, tool_name: str, args: dict[str, Any]) -> list[tuple]:
        _PREFERRED_ORDER = {
            'read_file': ['path', 'offset', 'limit'],
        }
        preferred = _PREFERRED_ORDER.get(tool_name, [])
        
        ordered: list[tuple[str, Any]] = []
        seen = set()
        
        for key in preferred:
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)
                
        remaining_keys = set(args.keys() - seen)
        for key in remaining_keys:
            if key in args:
                ordered.append((key, args[key]))
                
        return ordered
                
        
    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0,1))
        table.add_column(style='muted', justify='right', no_wrap=True)
        table.add_column(style='code', overflow="fold")
        
        for key, value in self._orderd_args(tool_name, args):
            pass

    def tool_call_start(
        self, call_id: str, name: str, tool_kind: str | None, arguments: dict[str, Any]
    ) -> None:
        self._tool_args_by_call_id[call_id] = arguments
        border_style = f"tool.{tool_kind}" if tool_kind else "tool"
        
        title = Text.assemble(
            ("⌛️ ", "muted"),
            (name, "tool"),
            ("  ", "muted"),
            (f"#{call_id[:8]}", "muted"),
        )
        
        panel = Panel(
            title=title,
        )
