"""Directory remove tool for MCP tools server."""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class DirectoryRemoveTool(BaseTool):
    """Tool for removing directories."""

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="directory_remove",
            description="Remove a directory",
            security_validator=security_validator
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Relative path to the directory to remove (e.g., 'dirname', 'parent/dirname')"
                }
            },
            "required": ["directory_path"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the directory remove tool."""
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

            return await self._remove_directory(path)

        except Exception as e:
            logger.error(f"Error in directory_remove tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }

    async def _remove_directory(self, path: Path) -> Dict[str, Any]:
        """Remove a directory."""
        try:
            if not path.exists():
                return {
                    "success": True,
                    "message": f"Directory does not exist (already removed): {self._normalize_path_for_response(path)}",
                    "directory_path": self._normalize_path_for_response(path),
                    "was_removed": False
                }

            if not path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {self._normalize_path_for_response(path)}"
                }

            # Check if directory is empty
            try:
                contents = list(path.iterdir())
                is_empty = len(contents) == 0
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied accessing directory: {self._normalize_path_for_response(path)}"
                }

            # Remove the directory (force remove if not empty)
            if not is_empty:
                shutil.rmtree(path)
                logger.info(f"Removed non-empty directory: {path}")
            else:
                path.rmdir()
                logger.info(f"Removed empty directory: {path}")

            return {
                "success": True,
                "message": f"Successfully removed directory: {self._normalize_path_for_response(path)}",
                "directory_path": self._normalize_path_for_response(path),
                "was_removed": True,
                "was_empty": is_empty
            }

        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied removing directory: {self._normalize_path_for_response(path)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to remove directory: {str(e)}"
            }
