"""The only shop-data boundary used by the PydanticAI agents."""

import json
from pathlib import Path
from typing import Any

from fastmcp import Client


MCP_SERVER_PATH = Path(__file__).resolve().parents[1] / "mcp_server" / "server.py"


class ShopMCPClient:
    """Call the existing FastMCP server; this class never opens SQLite."""

    async def call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        async with Client(MCP_SERVER_PATH) as client:
            result = await client.call_tool(tool_name, arguments or {})
        if getattr(result, "is_error", False):
            raise RuntimeError(f"MCP tool {tool_name} failed")
        structured = getattr(result, "structured_content", None)
        if structured is not None:
            return dict(structured)
        for item in getattr(result, "content", []):
            text = getattr(item, "text", None)
            if text:
                parsed = json.loads(text)
                return dict(parsed)
        return {}
