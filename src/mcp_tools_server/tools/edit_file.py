"""String-replacement based file editor for MCP tools server."""

import logging
from pathlib import Path
from typing import Dict, Any

import aiofiles

from .base import BaseTool
from ..security.validator import SecurityValidator
from ..core.structured_logger import logger


class EditFileTool(BaseTool):
    """Edit files using exact string replacement.

    Finds ``old_content`` in the file and replaces it with ``new_content``.
    By default the call is rejected when ``old_content`` matches more than
    one location — the model must then supply enough surrounding context to
    make the match unique.  Pass ``replace_all=true`` to replace every
    occurrence intentionally (useful for renaming a variable, updating an
    import path, etc.).
    """

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="edit_file",
            description=(
                "Edit a file by replacing an exact string. "
                "Provide old_content (the exact text to find) and new_content "
                "(the replacement). Fails if old_content is not found or matches "
                "more than one location — add surrounding context to make it "
                "unique, or set replace_all=true to replace every occurrence."
            ),
            security_validator=security_validator,
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_content": {
                    "type": "string",
                    "description": (
                        "Exact text to find in the file. Must match exactly once "
                        "unless replace_all=true. Include surrounding lines for "
                        "context if the snippet might appear elsewhere."
                    ),
                },
                "new_content": {
                    "type": "string",
                    "description": "Text to replace old_content with.",
                },
                "replace_all": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "Replace every occurrence of old_content. "
                        "Default false (fails if more than one match)."
                    ),
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding (default: utf-8)",
                },
            },
            "required": ["file_path", "old_content", "new_content"],
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = params.get("file_path")
        old_content = params.get("old_content")
        new_content = params.get("new_content")
        replace_all = params.get("replace_all", False)
        encoding = params.get("encoding", "utf-8")

        if not file_path:
            return {"success": False, "error": "file_path is required"}
        if old_content is None:
            return {"success": False, "error": "old_content is required"}
        if new_content is None:
            return {"success": False, "error": "new_content is required"}

        try:
            validated_path = self.security_validator.validate_file_path(file_path)
        except Exception as e:
            return {"success": False, "error": f"Security error: {e}"}

        try:
            async with aiofiles.open(validated_path, "r", encoding=encoding) as f:
                content = await f.read()
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {file_path}"}
        except UnicodeDecodeError as e:
            return {"success": False, "error": f"Encoding error: {e}"}

        count = content.count(old_content)

        if count == 0:
            return {"success": False, "error": "old_content not found in file"}

        if count > 1 and not replace_all:
            return {
                "success": False,
                "error": (
                    f"old_content matches {count} locations — add more surrounding "
                    f"context to make it unique, or set replace_all=true to replace all"
                ),
            }

        new_file_content = content.replace(old_content, new_content)

        try:
            async with aiofiles.open(validated_path, "w", encoding=encoding) as f:
                await f.write(new_file_content)
        except Exception as e:
            return {"success": False, "error": f"Failed to write file: {e}"}

        replacements = count if replace_all else 1
        self.log_tool_result({
            "success": True,
            "replacements": replacements,
            "path": self._normalize_path_for_response(validated_path),
        })
        return {
            "success": True,
            "file_path": self._normalize_path_for_response(validated_path),
            "replacements": replacements,
            "size_bytes": validated_path.stat().st_size,
        }
