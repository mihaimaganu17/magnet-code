import asyncio
import json
import os
import signal
import sys
import tempfile
from typing import Any
from magnet_code.config.config import (
    Config,
    HookConfig,
    HookTrigger,
    ShellEnvironmentPolicy,
)
from magnet_code.tools.base import ToolResult


class HookSystem:
    def __init__(self, config: Config):
        self.config = config
        self.hooks: list[HookConfig] = []

        if self.config.hooks_enabled:
            self.hooks = [hook for hook in self.config.hooks if hook.enabled]

    async def _run_hook(self, hook: HookConfig, env: dict[str, str]) -> None:
        print(hook.command)
        if hook.command:
            await self._run_command(hook.command, hook.timeout_sec, env)
        else:
            # running a .sh script
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh") as f:
                f.write("#!/bin/bash\n")
                f.write(hook.script)
                script_path = f.name
            try:
                os.chmod(script_path, 0o755)
                await self._run_command(script_path, hook.timeout_sec, env)
            finally:
                os.unlink(script_path)

    async def _run_command(self, command: str, timeout: float, env: dict[str, str]) -> None:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                # Capture the standard output and error
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.cwd,
                env=env,
                # Create a new OS session and process group
                start_new_session=True,
            )
            print(process)

            try:
                await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # If we have a timeout error, force kill the shell
                if sys.platform != "win32":
                    os.killpg(os.getpgid(process), signal.SIGKILL)
                else:
                    process.kill()
                await process.wait()
        except Exception as e:
            print(e)

    def _build_env(
        self,
        trigger: HookTrigger,
        tool_name: str | None,
        user_message: str | None = None,
        error: Exception | None = None,
    ) -> dict[str, str]:
        env = ShellEnvironmentPolicy(ignore_default_excludes=True)._build_environment()
        env['MAGNET_TRIGGER'] = trigger.value
        env['MAGNET_CWD'] = str(self.config.cwd)

        if tool_name:
            env['MAGNET_TOOL_NAME'] = tool_name

        if user_message:
            env['MAGNET_USER_MESSAGE'] = user_message

        if error:
            env["MAGNET_ERROR"] = str(error)

        return env

    async def trigger_before_agent(self, user_message: str) -> None:
        env = self._build_env(HookTrigger.BEFORE_AGENT, user_message)
        for hook in self.hooks:
            if hook.trigger == HookTrigger.BEFORE_AGENT:
                await self._run_hook(hook, env)

    async def trigger_after_agent(self, user_message: str, agent_response: str) -> None:
        env = self._build_env(HookTrigger.AFTER_AGENT, user_message)
        env['MAGNET_RESPONSE'] = agent_response

        for hook in self.hooks:
            if hook.trigger == HookTrigger.AFTER_AGENT:
                await self._run_hook(hook, env)

    async def trigger_before_tool(self, tool_name: str, tool_params: dict[str, Any]) -> None:
        env = self._build_env(HookTrigger.BEFORE_TOOL, tool_name)
        env['MAGNET_TOOL_PARAMS'] = json.dumps(tool_params)

        for hook in self.hooks:
            if hook.trigger == HookTrigger.BEFORE_TOOL:
                await self._run_hook(hook, env)

    async def trigger_after_tool(self, tool_name: str, tool_params: dict[str, Any], tool_result: ToolResult) -> None:
        env = self._build_env(HookTrigger.AFTER_TOOL, tool_name)
        env['MAGNET_TOOL_PARAMS'] = json.dumps(tool_params)
        env['MAGNET_TOOL_RESULT'] = tool_result.to_model_output()

        for hook in self.hooks:
            if hook.trigger == HookTrigger.AFTER_TOOL:
                await self._run_hook(hook, env)

    async def trigger_on_error(self, error: Exception) -> None:
        env = self._build_env(HookTrigger.ON_ERROR, error)
        for hook in self.hooks:
            if hook.trigger == HookTrigger.ON_ERROR:
                await self._run_hook(hook, env)