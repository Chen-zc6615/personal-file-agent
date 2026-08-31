from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


async def load_mcp_tools(
        connections: dict[str, dict[str, Any]],
) -> list[BaseTool]:
    """Connect to MCP servers and load their tools."""

    if not connections:
        return []

    client = MultiServerMCPClient(connections)

    return await client.get_tools()