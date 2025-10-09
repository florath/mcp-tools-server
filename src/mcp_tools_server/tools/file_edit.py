"""Simple file edit tool for MCP tools server."""

import logging
from pathlib import Path
from typing import Dict, Any

import aiofiles

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class FileEditTool(BaseTool):
    """Tool for simple file editing - replace entire file content."""

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="file_edit",
            description="Edit file by replacing its entire content",
            security_validator=security_validator
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Relative path to the file to edit (e.g., 'file.txt', 'dir/file.txt')"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content to replace the entire file with"
                }
            },
            "required": ["file_path", "new_content"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the file edit tool."""
        try:
            file_path = params.get('file_path')
            new_content = params.get('new_content')

            if not file_path:
                return {
                    "success": False,
                    "error": "file_path parameter is required"
                }

            if new_content is None:
                return {
                    "success": False,
                    "error": "new_content parameter is required"
                }

            # Security validation
            try:
                validated_path = self.security_validator.validate_file_path(file_path)
            except (ValueError, Exception) as e:
                return {
                    "success": False,
                    "error": f"Security validation failed: {str(e)}"
                }

            # Read old content for verification
            try:
                async with aiofiles.open(validated_path, 'r', encoding='utf-8') as f:
                    old_content = await f.read()
                old_lines = len(old_content.split('\n'))
            except FileNotFoundError:
                return {
                    "success": False,
                    "error": f"File does not exist: {self._normalize_path_for_response(validated_path)}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to read file: {str(e)}"
                }

            # Write new content
            try:
                async with aiofiles.open(validated_path, 'w', encoding='utf-8') as f:
                    await f.write(new_content)
                new_lines = len(new_content.split('\n'))
                logger.info(f"Edited file: {validated_path}")
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to write file: {str(e)}"
                }

            return {
                "success": True,
                "message": f"Successfully edited file: {self._normalize_path_for_response(validated_path)}",
                "file_path": self._normalize_path_for_response(validated_path),
                "old_lines": old_lines,
                "new_lines": new_lines,
                "size_bytes": validated_path.stat().st_size
            }

        except Exception as e:
            logger.error(f"Error in file_edit tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
