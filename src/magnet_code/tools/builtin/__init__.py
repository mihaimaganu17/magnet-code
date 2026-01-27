from magnet_code.tools.base import Tool
from magnet_code.tools.builtin.read_file import ReadFileTool

__all__ = [
    'ReadFileTool'
]

def get_all_builtin_tools() -> list[type]:
    return [
        ReadFileTool,
    ]