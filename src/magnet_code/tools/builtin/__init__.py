from magnet_code.tools.builtin.edit_file import EditTool
from magnet_code.tools.builtin.glob import GlobTool
from magnet_code.tools.builtin.grep import GrepTool
from magnet_code.tools.builtin.list_dir import ListDirTool
from magnet_code.tools.builtin.read_file import ReadFileTool
from magnet_code.tools.builtin.shell import ShellTool
from magnet_code.tools.builtin.web_search import WebSearchTool
from magnet_code.tools.builtin.write_file import WriteFileTool

__all__ = [
    'ReadFileTool',
    "WriteFileTool",
    "EditTool",
    "ShellTool",
    "ListDirTool",
    "GrepTool",
    "GlobTool",
    "WebSearchTool",
]

def get_all_builtin_tools() -> list[type]:
    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
        ListDirTool,
        GrepTool,
        GlobTool,
        WebSearchTool,
    ]