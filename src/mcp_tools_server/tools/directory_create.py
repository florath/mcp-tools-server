"""Directory create tool for MCP tools server."""

import logging
from pathlib import Path
from typing import Dict, Any

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class DirectoryCreateTool(BaseTool):
    """Tool for creating directories."""

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="directory_create",
            description="Create a new directory",
            security_validator=security_validator
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Relative path to the directory to create (e.g., 'newdir', 'parent/newdir')"
                }
            },
            "required": ["directory_path"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the directory create tool."""
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

            return await self._create_directory(path)

        except Exception as e:
            logger.error(f"Error in directory_create tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }

    async def _create_directory(self, path: Path) -> Dict[str, Any]:
        """Create a directory."""
        try:
            if path.exists():
                if path.is_dir():
                    return {
                        "success": True,
                        "message": f"Directory already exists: {self._normalize_path_for_response(path)}",
                        "directory_path": self._normalize_path_for_response(path),
                        "already_existed": True
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Path exists but is not a directory: {self._normalize_path_for_response(path)}"
                    }

            # Create the directory with parents
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {path}")

            return {
                "success": True,
                "message": f"Successfully created directory: {self._normalize_path_for_response(path)}",
                "directory_path": self._normalize_path_for_response(path),
                "already_existed": False
            }

        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied creating directory: {self._normalize_path_for_response(path)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create directory: {str(e)}"
            }
