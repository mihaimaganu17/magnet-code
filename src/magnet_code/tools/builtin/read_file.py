from pydantic import BaseModel, Field

from magnet_code.tools.base import Tool, ToolKind


class ReadFileParams(BaseModel):
    path: str = Field(
        ...,
        description="Path to the file to read (relative to working directory or absolute)",
    )
    line: int = Field(
        1, ge=1, description="Line number to start reading from (1-based) Defaults to 1"
    )
    limit: int | None = Field (
        None,
        ge=1,
        description="Maximum number of lines to read. If not specified, reads entire file."
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