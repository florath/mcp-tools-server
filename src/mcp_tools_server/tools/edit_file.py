"""Line-number based file editor for MCP tools server."""

import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiofiles

from .base import BaseTool
from ..security.validator import SecurityValidator


from ..core.structured_logger import logger


class EditFileTool(BaseTool):
    """Edit files using line-number based operations.

    Supports three operations:
    - ``edit``   — replace a line range (requires old_content for verification)
    - ``insert`` — insert text before a given line (or append after last line)
    - ``delete`` — delete a line range (requires old_content for verification)

    Using line numbers avoids the duplicate-string ambiguity problem: if the
    same text appears on multiple lines only the targeted line is touched.
    ``old_content`` verification on edit/delete prevents silent overwrites when
    the file has changed since it was last read.
    """

    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="edit_file",
            description=(
                "Edit a file by line number: replace, insert, or delete lines. "
                "Use read_file with include_line_numbers=True first to get "
                "the exact line numbers. old_content is required for edit/delete "
                "to verify you are changing the right lines."
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
                "operation": {
                    "type": "string",
                    "enum": ["edit", "insert", "delete"],
                    "description": (
                        "'edit': replace lines line_number..line_end with new_content. "
                        "'insert': insert new_content before line_number "
                        "(use line_number = total_lines+1 to append). "
                        "'delete': delete lines line_number..line_end."
                    ),
                },
                "line_number": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Start line (1-indexed)",
                },
                "line_end": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "End line for range operations (inclusive, defaults to line_number)",
                },
                "old_content": {
                    "type": "string",
                    "description": "Expected current content of the targeted lines (required for edit/delete)",
                },
                "new_content": {
                    "type": "string",
                    "description": "Replacement or insertion text (required for edit/insert)",
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding (default: utf-8)",
                },
            },
            "required": ["file_path", "operation", "line_number"],
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = params.get("file_path")
        operation = params.get("operation")
        line_number = params.get("line_number")
        line_end = params.get("line_end")
        old_content = params.get("old_content")
        new_content = params.get("new_content", "")
        encoding = params.get("encoding", "utf-8")

        if not file_path:
            return {"success": False, "error": "file_path is required"}
        if operation not in ("edit", "insert", "delete"):
            return {"success": False, "error": "operation must be 'edit', 'insert', or 'delete'"}
        if line_number is None:
            return {"success": False, "error": "line_number is required"}

        # Infer line_end from old_content when not explicitly provided.
        # This lets callers omit line_end for multi-line edits/deletes —
        # they just supply old_content and the range is computed automatically.
        if line_end is None and old_content is not None:
            line_end = line_number + len(old_content.splitlines()) - 1

        if line_end is not None and line_end < line_number:
            return {"success": False, "error": "line_end must be >= line_number"}
        if operation in ("edit", "delete") and old_content is None:
            return {"success": False, "error": f"old_content is required for '{operation}'"}
        if operation in ("edit", "insert") and new_content is None:
            return {"success": False, "error": f"new_content is required for '{operation}'"}

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

        lines: List[str] = content.splitlines(keepends=True)
        total = len(lines)

        if operation == "insert":
            if line_number > total + 1:
                return {
                    "success": False,
                    "error": f"line_number {line_number} out of range (file has {total} lines; use {total+1} to append)",
                }
            insert_text = new_content if new_content.endswith("\n") else new_content + "\n"
            lines = lines[:line_number - 1] + [insert_text] + lines[line_number - 1:]

        else:  # edit or delete
            end_idx = (line_end if line_end is not None else line_number)
            if line_number > total:
                return {"success": False, "error": f"line_number {line_number} out of range (file has {total} lines)"}
            if end_idx > total:
                return {"success": False, "error": f"line_end {end_idx} out of range (file has {total} lines)"}

            # Verify old_content against the targeted lines
            targeted = "".join(lines[line_number - 1: end_idx])
            if targeted.rstrip("\n") != old_content.rstrip("\n"):
                return {
                    "success": False,
                    "error": (
                        "old_content does not match the file at the specified lines — "
                        "re-read the file to get the current content"
                    ),
                }

            if operation == "edit":
                replacement = new_content if new_content.endswith("\n") else new_content + "\n"
                lines = lines[:line_number - 1] + [replacement] + lines[end_idx:]
            else:  # delete
                lines = lines[:line_number - 1] + lines[end_idx:]

        new_content_str = "".join(lines)
        try:
            async with aiofiles.open(validated_path, "w", encoding=encoding) as f:
                await f.write(new_content_str)
        except Exception as e:
            return {"success": False, "error": f"Failed to write file: {e}"}

        self.log_tool_result({"success": True, "operation": operation, "path": self._normalize_path_for_response(validated_path)})
        return {
            "success": True,
            "file_path": self._normalize_path_for_response(validated_path),
            "operation": operation,
            "line_number": line_number,
            "line_end": line_end or line_number,
            "total_lines": len(lines),
            "size_bytes": validated_path.stat().st_size,
        }
