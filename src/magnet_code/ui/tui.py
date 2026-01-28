from pathlib import Path
from typing import Any
from rich.console import Console
from rich.theme import Theme
from rich.rule import Rule
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box

from magnet_code.tools.base import ToolResult
from magnet_code.utils.paths import resolve_path

import re

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
        # Marks if the assistant stream is currently being streamed up on display
        self._assistant_stream_open = False
        self._tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self.cwd = Path.cwd()

    def begin_assitant(self) -> None:
        """Assistant is starting to respond, so we update the internal state for that and print
        a visual indicator start"""
        self.console.print()
        self.console.print(Rule(Text("Assistant", style="assistant")))
        self._assistant_stream_open = True

    def end_assistant(self) -> None:
        """Assistant has finished streaming the response so we update the internal state
        accordingly"""
        if self._assistant_stream_open:
            self.console.print()
        self._assistant_stream_open = False

    def stream_assistant_delta(self, content: str) -> None:
        """Prints the streaming text delta sent from the assistant"""
        self.console.print(content, end="", markup=False)

    def _ordered_args(self, tool_name: str, args: dict[str, Any]) -> list[tuple]:
        # TODO: Document the parameters of this function
        """Order the arguments from a tool call received from the model in a preferred order
        depending on the tool

        :param tool_name: name of the tool that is being called
        :param args: argument dict where each key is the argument name and each value is the value
        of the argument
        :return: list of tuples ordered in the prefered order where each tuple has the following
        elements:
            argument name
            argument value
        """
        _PREFERRED_ORDER = {
            "read_file": ["path", "offset", "limit"],
        }

        preferred = _PREFERRED_ORDER.get(tool_name, [])

        # Keeps a list of ordered arguments and their value in a tuple
        ordered: list[tuple[str, Any]] = []
        # Keeps track of the seen arguments, such that if the preferred order of argument is
        # non-exhaustive, we do not miss additional arguments
        seen = set()

        # Process the preferred arguments first
        for key in preferred:
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)

        # Process the rest of the argumenst
        remaining_keys = set(args.keys() - seen)
        for key in remaining_keys:
            if key in args:
                ordered.append((key, args[key]))

        return ordered

    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        """Render an arguments table for of a function call to display in the TUI"""
        table = Table.grid(padding=(0, 1))
        # Argument name column
        table.add_column(style="muted", justify="right", no_wrap=True)
        # Argument value column
        table.add_column(style="code", overflow="fold")

        for key, value in self._ordered_args(tool_name, args):
            table.add_row(key, value)

        return table

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

        display_args = dict(arguments)
        for key in ("path", "cwd"):
            val = display_args.get(key)
            if isinstance(val, str) and self.cwd:
                display_args[key] = str(resolve_path(self.cwd, val))

        panel = Panel(
            (
                self._render_args_table(name, display_args)
                if display_args
                else Text("(no args)", style="muted")
            ),
            title=title,
            title_align="left",
            subtitle=Text("running", style="muted"),
            subtitle_align="right",
            box=box.ROUNDED,
            border_style=border_style,
            padding=(1, 2),
        )

        self.console.print()
        self.console.print(panel)

    def _extract_read_file_code(self, text: str) -> tuple[int, str] | None:
        body = text
        header_match = re.match(r"^Showing lines (\d+)-(\d+) of (\d+)\n\n", text)

        if header_match:
            # Skip the header if it exists
            body = text[header_match.end() :]

        code_lines: list[str] = []
        start_line: int | None = None
        
        for line in body.splitlines():
            m = re.match(r"^\s*(\d+)\|(.*)$", line)
            if not m:
                return None
            line_number = int(m.group(1))
            if start_line is None:
                start_line = line_number
            code_lines.append(m.group(2))
            
        if start_line is None:
            return None
        
        return start_line, "\n".join(code_lines)


    def tool_call_complete(self, call_id: str, name: str, result: ToolResult) -> None:
        status_icon = "✅" if result.success else "❌"
        status_style = "success" if result.success else "error"

        title = Text.assemble(
            (f"{status_icon}", f"{status_style}"),
            (name, "tool"),
            ("  ", "muted"),
            (f"#{call_id[:8]}", "muted"),
        )
        
        primary_path = None
        if isinstance(result.metadata, dict) and isinstance(result.metadata.get('path'), str):
            primary_path = result.metadata.get("path")

        if name == "read_file" and result.success:
            start_line, code = self._extract_read_file_code(result.output)
            
            shown_start = result.metadata.get('shown_start')
            shown_end = result.metadata.get('shown_end')
            total_lines = result.metadata.get('total_lines')


        display_args = dict(arguments)
        for key in ("path", "cwd"):
            val = display_args.get(key)
            if isinstance(val, str) and self.cwd:
                display_args[key] = str(resolve_path(self.cwd, val))

        panel = Panel(
            (
                self._render_args_table(name, display_args)
                if display_args
                else Text("(no args)", style="muted")
            ),
            title=title,
            title_align="left",
            subtitle=Text("running", style="muted"),
            subtitle_align="right",
            box=box.ROUNDED,
            border_style=border_style,
            padding=(1, 2),
        )

        self.console.print()
        self.console.print(panel)
