"""MCP server exposing file-management tools."""

from mcp.server.fastmcp import FastMCP

from assistant.file_management import (
    apply_file_organization,
    apply_file_renames,
    create_file_archive,
    find_duplicate_files,
    plan_file_archive,
    plan_file_organization,
    plan_file_renames,
)


mcp = FastMCP("File Organizer")

mcp.tool()(plan_file_organization)
mcp.tool()(apply_file_organization)
mcp.tool()(find_duplicate_files)
mcp.tool()(plan_file_renames)
mcp.tool()(apply_file_renames)
mcp.tool()(plan_file_archive)
mcp.tool()(create_file_archive)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
