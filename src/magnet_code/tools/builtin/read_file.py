from pydantic import BaseModel, Field

from magnet_code.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from magnet_code.utils.paths import is_binary_file, resolve_path
from magnet_code.utils.text import count_tokens, truncate_text


class ReadFileParams(BaseModel):
    path: str = Field(
        ...,
        description="Path to the file to read (relative to working directory or absolute)",
    )
    line: int = Field(
        1,
        ge=1,
        description="Line number to start reading from (1-based). Defaults to 1.",
    )
    limit: int | None = Field(
        None,
        ge=1,
        description="Maximum number of lines to read. If not specified, reads the entire file.",
    )


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Reads the contents of a text file. Returns the file content with line numbers. "
        "For large files, use line and limit paramteres to read specific portions. "
        "Cannot read binary files (images, executables, etc.)."
    )
    kind = ToolKind.READ
    schema = ReadFileParams

    # 10 MB max file size for a file read
    MAX_FILE_SIZE = 1024 * 1024 * 10
    MAX_OUTPUT_TOKENS = 25000

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        # TODO: Should we validate the parameters first?
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

        if is_binary_file(path):
            return ToolResult.error_result(
                f"Cannot read binary file: {path.name}"
                f"This tool only reads text files."
            )

        try:
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")

            lines = content.splitlines()
            total_lines = len(lines)

            if total_lines == 0:
                return ToolResult.success_result(
                    "File is empty.",
                    metadata={
                        "lines": 0,
                    },
                )

            start_idx = max(0, params.line - 1)

            if params.limit is not None:
                end_idx = min(start_idx + params.limit, total_lines)
            else:
                end_idx = total_lines

            selected_lines = lines[start_idx:end_idx]
            formatted_lines = []

            for i, line in enumerate(selected_lines, start=start_idx):
                formatted_lines.append(f"{i:6}|{line}")

           
            # TODO: How do we pass model here?
            model = "gpt-o1" 
            output = "\n".join(formatted_lines)
            token_count = count_tokens(output, model)

            truncated = False
            if token_count > self.MAX_OUTPUT_TOKENS:
                output = truncate_text(
                    output,
                    model,
                    self.MAX_OUTPUT_TOKENS,
                    suffix=f"\n... [truncated {total_lines} total lines]",
                )
                truncated = True

            metadata_lines = []
            if start_idx > 0 and end_idx < total_lines:
                metadata_lines.append(
                    f"Showing lines {start_idx + 1} - {end_idx} of {total_lines} total lines."
                )

            if metadata_lines:
                header = " | ".join(metadata_lines) + "\n\n"
                output = header + output

            return ToolResult.success_result(
                output=output,
                truncated=truncated,
                metadata={
                    "path": str(path),
                    "total_lines": total_lines,
                    "shown_start": start_idx + 1,
                    "shown_end": end_idx,
                },
            )
        except Exception as e:
            return ToolResult.error_result(f"Failed to read file: {e}")