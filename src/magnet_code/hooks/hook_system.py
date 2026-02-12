import asyncio
import os
import signal
import sys
import tempfile
from magnet_code.config.config import (
    Config,
    HookConfig,
    HookTrigger,
    ShellEnvironmentPolicy,
)


class HookSystem:
    def __init__(self, config: Config):
        self.config = config
        self.hooks: list[HookConfig] = []

        if not self.config.hooks_enabled:
            self.hooks = [hook for hook in self.config.hooks if hook.enabled]

    async def _run_hook(self, hook: HookConfig, env: dict[str, str]) -> None:
        if hook.command:
            await self._run_command(*hook.command, hook.timeout_sec, env)
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
        process = await asyncio.create_subprocess_exec(
            command,
            # Capture the standard output and error
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.cwd,
            env=env,
            # Create a new OS session and process group
            start_new_session=True,
        )

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
            env["MAGNET_ERROR"] = error

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