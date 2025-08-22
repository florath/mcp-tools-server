"""MCP Tools Server - Secure HTTP server for meta-cognitive agent tools."""

__version__ = "0.1.0"

# Programmatic API exports
from .api import MCPServerManager, managed_mcp_server, find_available_port

__all__ = ["MCPServerManager", "managed_mcp_server", "find_available_port"]