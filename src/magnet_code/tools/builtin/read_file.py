from pydantic import BaseModel, Field

from magnet_code.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from magnet_code.utils.paths import resolve_path


class ReadFileParams(BaseModel):
    path: str = Field(
        ...,
        description="Path to the file to read (relative to working directory or absolute)",
    )
    line: int = Field(
        1, ge=1, description="Line number to start reading from (1-based) Defaults to 1"
    )
    limit: int | None = Field(
        None,
        ge=1,
        description="Maximum number of lines to read. If not specified, reads entire file.",
    )


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the contents of a text file. Returns the file content with line numbers. "
        "For large files, use line and limit to read specific poritions. "
        "Cannot read binary files (images, executables, etc.)."
    )
    kind = ToolKind.READ
    schema = ReadFileParams

    # 10 MB max file size for a file read
    MAX_FILE_SIZE = 1024 * 1024 * 10

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ReadFileParams(**invocation.parameters)
        path = resolve_path(invocation.cwd, params.path)

        if not path.exists():
            return ToolResult.error_result(f"File not found: {path}")

        if not path.is_file():
            return ToolResult.error_result(f"Path is not a file: {path}")

        file_size = path.stat().st_size

        if file_size > self.MAX_FILE_SIZE:
            return ToolResult.error_result(
                f"File too large ({file_size / (1024*1024):.1f} MB)."
                f"Maximum is {self.MAX_FILE_SIZE / (1024*1024):.0f} MB."
            )
