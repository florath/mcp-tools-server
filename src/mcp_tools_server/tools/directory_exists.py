"""Directory exists tool for MCP tools server."""

import logging
from pathlib import Path
from typing import Dict, Any

from .base import BaseTool
from ..security.validator import SecurityValidator


from ..core.structured_logger import logger


class DirectoryExistsTool(BaseTool):
    """Tool for checking if a directory exists."""

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="directory_exists",
            description="Check if a directory exists",
            security_validator=security_validator
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Relative path to check for existence (e.g., '.', 'subdir')"
                }
            },
            "required": ["directory_path"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the directory exists tool."""
        try:
            directory_path = params.get('directory_path')

            if not directory_path:
                return {
                    "success": False,
                    "error": "directory_path parameter is required"
                }

            # Security validation and path resolution
            try:
                path = self.security_validator.validate_directory_path_for_creation(directory_path)
            except (ValueError, Exception) as e:
                return {
                    "success": False,
                    "error": f"Security validation failed: {str(e)}"
                }

            return await self._check_exists(path)

        except Exception as e:
            self.log_tool_error(str(e), params)
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }

    async def _check_exists(self, path: Path) -> Dict[str, Any]:
        """Check if a directory exists."""
        try:
            exists = path.exists()
            is_directory = path.is_dir() if exists else False

            return {
                "success": True,
                "message": f"Checked existence of: {self._normalize_path_for_response(path)}",
                "directory_path": self._normalize_path_for_response(path),
                "exists": exists,
                "is_directory": is_directory
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to check directory existence: {str(e)}"
            }
