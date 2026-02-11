from pathlib import Path
from pydantic import BaseModel, Field
from magnet_code.tools.base import (
    FileDiff,
    Tool,
    ToolConfirmation,
    ToolInvocation,
    ToolKind,
    ToolResult,
)
from magnet_code.utils.paths import ensure_parent_directory, resolve_path


class EditParams(BaseModel):
    path: str = Field(
        ...,
        description="Path to the file to edit (relative to working directory or absolute path)",
    )
    old_string: str = Field(
        "",
        description="The exact text to find and replace. Must match exactly including all whitespace and indentation. For new files, leave this empty.",
    )
    new_string: str = Field(
        ...,
        description="The text to replace old_strin with. Can be empty to delete text.",
    )
    replace_all: bool = Field(
        False, description="Replace all occurences of old_string (default: False)"
    )


class EditTool(Tool):
    name = "edit"
    description = (
        "Edit a file by replacing text. The old_string much match exactly (including whitespace "
        "and indentation) and must be unique in the file unless replace_all is true. Use this for "
        "precise edits. For creating new files or complete rewrites, use write_file instead."
    )
    kind = ToolKind.WRITE
    schema = EditParams

    async def get_confirmation(self, invocation) -> ToolConfirmation:
        params = EditParams(**invocation.parameters)
        path = resolve_path(invocation.cwd, params.path)

        is_new_file = not path.exists()

        if is_new_file:
            diff = FileDiff(
                path=path,
                old_content="",
                new_content=params.new_string,
                is_new_file=is_new_file,
            )

            return ToolConfirmation(
                tool_name=self.name,
                params=invocation.parameters,
                description=f"Created file: {path}",
                diff=diff,
                affected_paths=[path],
                is_dangerous=True,
            )

        old_content = path.read_text(encoding="utf-8")

        if params.replace_all:
            new_content = old_content.replace(params.old_string, params.new_string)
        else:
            new_content = old_content.replace(params.old_string, params.new_string, 1)

        diff = (
            FileDiff(
                path=path,
                old_content=old_content,
                new_content=params.content,
                is_new_file=is_new_file,
            ),
        )

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.parameters,
            description=f"Edit file: {path}",
            diff=diff,
            affected_paths=[path],
            is_dangerous=True,
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = EditParams(**invocation.parameters)
        path = resolve_path(invocation.cwd, params.path)

        # Handling non-exitent path by creating a new file with the new_string
        if not path.exists():
            # If path does not exist, but the old_string does, the LLM hallucinated.
            if params.old_string:
                return ToolResult.error_result(
                    f"File does not exist: {path}. To create a new file, use an empty old_string instead."
                )
            ensure_parent_directory(path)
            path.write_text(params.new_string, encoding="utf-8")

            line_count = len(params.new_string.splitlines())

            return ToolResult.success_result(
                f"Created {path} {line_count} lines",
                diff=FileDiff(
                    path=path,
                    old_content="",
                    new_content=params.new_string,
                    is_new_file=True,
                ),
                metadata={
                    "path": str(path),
                    "is_new_file": True,
                    "lines": line_count,
                },
            )

        old_content = path.read_text(encoding="utf-8")

        if not params.old_string:
            return ToolResult.error_result(
                "old_string is empty but file exists. Provide old_string to edit, or use write_file tool instead"
            )

        occurrence_count = old_content.count(params.old_string)

        # If the string we are trying to edit is not present in the file, the LLM hallucinates or
        # does not have the last updated state
        if occurrence_count == 0:
            return self._no_match_error(params.old_string, old_content, path)

        if occurrence_count > 1 and not params.replace_all:
            return ToolResult.error_result(
                f"old_string found {occurrence_count} times in {path}."
                f"Either: \n"
                f"1. Provide more context to make the match unique or\n"
                f"2. Set replace_all=true to replace all occurrences",
                metadata={
                    "ocurrence_count": occurrence_count,
                },
            )

        if params.replace_all:
            new_content = old_content.replace(params.old_string, params.new_string)
            replace_count = occurrence_count
        else:
            new_content = old_content.replace(params.old_string, params.new_string, 1)
            replace_count = 1

        # TODO: Should we do this above by comparing new_string and old_string before replacing?
        if new_content == old_content:
            return ToolResult.error_result(
                "No change made - old_string equals new_string"
            )

        try:
            path.write_text(new_content, encoding="utf-8")
        except IOError as e:
            return ToolResult.error_result(f"Failed to write file: {e}")

        # Keeps track of how many lines were added / removed
        old_lines = len(old_content.splitlines())
        new_lines = len(new_content.splitlines())
        line_diff = new_lines - old_lines
        diff_msg = ""

        if line_diff > 0:
            diff_msg = f" (+{line_diff} lines)"
        elif line_diff < 0:
            diff_msg = f" ({line_diff} lines)"

        return ToolResult.success_result(
            f"Edited {path}: replaced: {replace_count} occurrence(s){diff_msg}",
            diff=FileDiff(
                path=path,
                old_content=old_content,
                new_content=new_content,
            ),
            metadata={
                "path": str(path),
                "replaced_count": replace_count,
                "line_diff": line_diff,
            },
        )

    def _no_match_error(self, old_string: str, content: str, path: Path) -> ToolResult:
        lines = content.splitlines()

        # We want to be able to search for potential partial matches in order to give the LLM a clue
        # about what it could be searching for
        partial_matches = []
        search_terms = old_string.split()[:5]

        if search_terms:
            first_term = search_terms[0]
            for i, line in enumerate(lines, 1):
                # If we find the term on this line
                if first_term in line:
                    # We save the line and the line number
                    partial_matches.append((i, line.strip()[:80]))
                    if len(partial_matches) >= 3:
                        break

        error_msg = f"old_string not found in {path}."

        if partial_matches:
            # Report possible matching lines in the error message
            error_msg += "\n\nPossible similar lines:"
            for line_num, line_preview in partial_matches:
                error_msg += f"\n Line {line_num}: {line_preview}"
            error_msg += "\n\nMake sure old_string matches exactly (including whitespace and indentation)."
        else:
            error_msg += (
                " Make sure the text matches exactly, including:\n"
                "- All whitespace and indentation\n"
                "- Line breaks\n"
                "- Any invisible characters"
                "- Try re-reading the file using read_file tool and then editing."
            )

        return ToolResult.error_result(error_msg)
