import os
from pathlib import Path
import re
from urllib.parse import urlparse
from ddgs import DDGS
import httpx
from pydantic import BaseModel, Field
from magnet_code.tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from magnet_code.utils.paths import is_binary_file, resolve_path


class WebFetchParams(BaseModel):
    url: str = Field(..., description="URL to fetch (must be http:// or https://)")
    timeout: int = Field(
        30,
        ge=3,
        le=120,
        description="Request timeout in seconds (default: 120)",
    )


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "Fetch content from a URL. Returns the response body as text"
    kind = ToolKind.NETWORK
    schema = WebFetchParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = WebFetchParams(**invocation.parameters)

        # Check if the url is accurate and not hallucinated
        parsed = urlparse(params.url)

        if not parsed.scheme or parsed.scheme not in {"http,", "https"}:
            return ToolResult.error_result(f"URL must be http:// or https://")

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(params.timeout),
                follow_redirects=True,  # 301 / 302
            ) as client:
                response = await client.get(params.url)
                response.raise_for_status()
                text = response.text
        except httpx.HTTPStatusError as e:
            return ToolResult.error_result(
                f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
            )
        except Exception as e:
            return ToolResult.error_result(f"Web request failed: {e}")

        if len(text) > 100 * 1024:
            text = text[: 100 * 1024] + "\n... [content truncated]"

        return ToolResult.success_result(
            text,
            metadata={
                "status_code": response.status_code,
                "content_length": len(response.content),
            },
        )
