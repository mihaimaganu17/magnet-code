import asyncio
import os
from pathlib import Path
import signal
import sys
from magnet_code.tools.base import Tool, ToolConfirmation, ToolInvocation, ToolKind, ToolResult
from pydantic import BaseModel, Field
import fnmatch

from magnet_code.utils.paths import resolve_path

BLOCKED_COMMANDS = {
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "mkfs",
    "fdisk",
    "parted",
    ":(){ :|:& };:",  # Fork bomb
    "chmod 777 /",
    "chmod -R 777",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
}


class ShellParams(BaseModel):
    command: str = Field(..., description="The shell command to execute")
    timeout: int = Field(
        120, ge=1, le=600, description="Timeout in seconds (default: 120)"
    )
    cwd: str | None = Field(None, description="Working directory for the command")


class ShellTool(Tool):
    name = "shell"
    kind = ToolKind.SHELL
    description = "Execute a shell command. Use this for running system commands, scripts and CLI tools."
    schema = ShellParams

    async def get_confirmation(self, invocation) -> ToolConfirmation:
        params = ShellParams(**invocation.parameters)

        command = params.command.lower().strip()
        
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return ToolConfirmation(
                    tool_name = self.name,
                    params = invocation.parameters,
                    description=f"Execute (BLOCKED): {command}",
                    command=params.command,
                    is_dangerous=True,
                )

        return ToolConfirmation(
            tool_name = self.name,
            params = invocation.parameters,
            description=f"Execut: {command}",
            command=params.command,
            is_dangerous=True,
        )

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ShellParams(**invocation.parameters)

        command = params.command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in command:
                return ToolResult.error_result(
                    f"Command blocked for safety: {params.command}",
                    metadata={"blocked": True},
                )

        if params.cwd:
            cwd = Path(params.cwd)

            # If the current working directory is realtive, use the invocation working directory as
            # base
            if not cwd.is_absolute():
                cwd = invocation.cwd / cwd

        else:
            cwd = invocation.cwd

        if not cwd.exists():
            return ToolResult.error_result(f"Working directory doesn't exist: {cwd}")

        env = self.config.shell_environment._build_environment()

        if sys.platform == "win32":
            shell_cmd = ["cmd.exe", "/c", params.command]
        else:
            shell_cmd = ["/bin/bash", "-c", params.command]

        # Print the shell environment and command and allow the user to press enter before
        # continuing
        print(env)
        print(shell_cmd)
        input("Press Enter to continue...")

        # Create a new process with the shell command
        process = await asyncio.create_subprocess_exec(
            *shell_cmd,
            # Capture the standard output and error
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            # Create a new OS session and process group
            start_new_session=True,
        )

        try:
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(),
                timeout=params.timeout,
            )
        except asyncio.TimeoutError:
            # If we have a timeout error, force kill the shell
            if sys.platform != "win32":
                os.killpg(os.getpgid(process), signal.SIGKILL)
            else:
                process.kill()
            await process.wait()
            return ToolResult.error_result(f"Command timed out after {params.timeout}")

        # Convert the data to string
        stdout = stdout_data.decode("utf-8", errors="replace")
        stderr = stderr_data.decode("utf-8", errors="replace")
        exit_code = process.returncode

        # Strip and collect the output
        output = ""
        if stdout.strip():
            output += stdout.rstrip()

        if stderr.strip():
            output += "\n--- stderr ---\n"
            output += stderr.rstrip()

        if exit_code != 0:
            output += f"\nExit code: {exit_code}"
            
        # If output is bigger than 1Kb
        if len(output) > 100 * 1024:
            output = output[:100 * 1024] + '\n... [output truncated]'
            
        return ToolResult(
            success=exit_code==0,
            error=stderr if exit_code != 0 else None,
            exit_code=exit_code,
            output=output,
        )
