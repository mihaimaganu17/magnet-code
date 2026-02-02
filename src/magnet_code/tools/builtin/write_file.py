from pydantic import BaseModel, Field
from magnet_code.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from magnet_code.utils.paths import ensure_parent_directory, resolve_path


class WriteFileParams(BaseModel):
    path: str = Field(
        ...,
        description="Path to the file to write (relative to the working directory or absolute)",
    )
    content: str = Field(..., description="Content to write to the file")
    create_directories: bool = Field(
        True, description="Create parent directories if they don't exist"
    )


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write content to a file. Creates the file if it doesn't exist, or overwrites if it does. "
        "Parent directories are created automatically. Use this for creating new files or "
        "completely replacing file contents. For partial modifications, use the edit tool instead."
    )
    kind = ToolKind.WRITE
    schema = WriteFileParams
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WriteFileParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)
        
        # Read potential existing content if the file already exists
        is_new_file = not path.exists()
        old_content = ""
        
        if not is_new_file:
            try:
                old_content = path.read_text(encoding='utf-8')
            except:
                pass
            
        try:
            if params.create_directories:
                ensure_parent_directory(path)
            elif not path.parent.exists():
                return ToolResult.error_result(f"Parent directory does not exist: {path.parent}")

            path.write_text(params.content, encoding="utf-8")
            
            action = "Created" if is_new_file else "Updated"
            line_count = len(params.content.splitlines())

            return ToolResult.success_result(
                f"{action} {path} {line_count} lines",
            )
        except OSError as e:
            return ToolResult.error_result(f"Failed to write file: {e}")
