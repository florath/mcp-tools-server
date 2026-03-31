"""Directory list tool for MCP tools server."""

import logging
from pathlib import Path
from typing import Dict, Any

from .base import BaseTool
from ..security.validator import SecurityValidator


from ..core.structured_logger import logger


class DirectoryListTool(BaseTool):
    """Tool for listing directory contents."""

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="directory_list",
            description="List contents of a directory",
            security_validator=security_validator
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Relative path to the directory to list (e.g., '.', 'subdir')"
                }
            },
            "required": ["directory_path"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the directory list tool."""
        # Log tool call
        self.log_tool_call(params)
        
        try:
            directory_path = params.get('directory_path')

            if not directory_path:
                return {
                    "success": False,
                    "error": "directory_path parameter is required"
                }

            # Security validation and path resolution
            try:
                path = self.security_validator.validate_directory_path(directory_path)
            except (ValueError, Exception) as e:
                return {
                    "success": False,
                    "error": f"Security validation failed: {str(e)}"
                }

            result = await self._list_directory(path)
            self.log_tool_result(result)
            return result

        except Exception as e:
            self.log_tool_error(str(e), params)
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }

    async def _list_directory(self, path: Path) -> Dict[str, Any]:
        """List directory contents."""
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Directory does not exist: {self._normalize_path_for_response(path)}"
                }

            if not path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {self._normalize_path_for_response(path)}"
                }

            # List contents
            contents = []
            try:
                for item in path.iterdir():
                    item_info = {
                        "name": item.name,
                        "path": self._normalize_path_for_response(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None
                    }
                    contents.append(item_info)
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied listing directory: {self._normalize_path_for_response(path)}"
                }

            # Sort by type (directories first), then by name
            contents.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))

            return {
                "success": True,
                "message": f"Successfully listed directory: {self._normalize_path_for_response(path)}",
                "directory_path": self._normalize_path_for_response(path),
                "contents": contents,
                "total_items": len(contents),
                "directories": len([c for c in contents if c["type"] == "directory"]),
                "files": len([c for c in contents if c["type"] == "file"])
            }

        except Exception as e:
            self.log_tool_error(str(e), {})
            return {
                "success": False,
                "error": f"Failed to list directory: {str(e)}"
            }
