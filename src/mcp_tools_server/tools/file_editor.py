"""File editor tool for MCP tools server."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiofiles

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class FileEditorTool(BaseTool):
    """Tool for editing files with line-number based operations."""
    
    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="file_editor",
            description="Edit files using line-number based operations (edit, insert, delete)",
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
                "operation": {
                    "type": "string",
                    "description": "Operation to perform: 'edit', 'insert', or 'delete'",
                    "enum": ["edit", "insert", "delete"]
                },
                "line_number": {
                    "type": "integer",
                    "description": "Line number to operate on (1-indexed)",
                    "minimum": 1
                },
                "line_end": {
                    "type": "integer",
                    "description": "End line number for range operations (1-indexed, inclusive)",
                    "minimum": 1
                },
                "old_content": {
                    "type": "string",
                    "description": "Expected old content (for verification before edit/delete)"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content to insert or replace with"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)",
                    "default": "utf-8"
                }
            },
            "required": ["file_path", "operation", "line_number"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the file editor tool."""
        try:
            file_path = params.get('file_path')
            operation = params.get('operation')
            line_number = params.get('line_number')
            line_end = params.get('line_end')
            old_content = params.get('old_content')
            new_content = params.get('new_content', '')
            encoding = params.get('encoding', 'utf-8')
            
            # Validate required parameters
            if not file_path:
                return {
                    "success": False,
                    "error": "file_path parameter is required"
                }
            
            if not operation:
                return {
                    "success": False,
                    "error": "operation parameter is required"
                }
                
            if line_number is None:
                return {
                    "success": False,
                    "error": "line_number parameter is required"
                }
                
            if line_number < 1:
                return {
                    "success": False,
                    "error": "line_number must be 1 or greater"
                }
            
            if line_end is not None and line_end < line_number:
                return {
                    "success": False,
                    "error": "line_end must be greater than or equal to line_number"
                }
            
            # Validate operation-specific parameters
            if operation in ['edit', 'delete'] and old_content is None:
                return {
                    "success": False,
                    "error": f"{operation} operation requires old_content for verification"
                }
                
            if operation in ['edit', 'insert'] and new_content is None:
                return {
                    "success": False,
                    "error": f"{operation} operation requires new_content"
                }
            
            # Security validation
            try:
                # For file editor, we validate the directory path for creation if file doesn't exist
                path = Path(file_path)
                if path.exists():
                    self.security_validator.validate_file_path(file_path)
                else:
                    # Validate the directory path and extension
                    self.security_validator.validate_directory_path_for_creation(str(path.parent))
                    if not self.security_validator._is_extension_allowed(path):
                        raise ValueError(f"File extension not allowed: {path.suffix}")
            except (ValueError, Exception) as e:
                return {
                    "success": False,
                    "error": f"Security validation failed: {str(e)}"
                }
            
            path = Path(file_path)
            
            if operation == "edit":
                return await self._edit_lines(path, line_number, line_end, old_content, new_content, encoding)
            elif operation == "insert":
                return await self._insert_lines(path, line_number, new_content, encoding)
            elif operation == "delete":
                return await self._delete_lines(path, line_number, line_end, old_content, encoding)
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}. Must be 'edit', 'insert', or 'delete'"
                }
                
        except Exception as e:
            logger.error(f"Error in file_editor tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def _read_file_lines(self, path: Path, encoding: str) -> List[str]:
        """Read file and return lines."""
        if not path.exists():
            return []  # File doesn't exist yet
        
        async with aiofiles.open(path, 'r', encoding=encoding) as f:
            content = await f.read()
            # Split and preserve line endings
            lines = content.splitlines(keepends=True)
            return lines
    
    async def _write_file_lines(self, path: Path, lines: List[str], encoding: str) -> None:
        """Write lines to file."""
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(path, 'w', encoding=encoding) as f:
            await f.writelines(lines)
    
    def _normalize_line_content(self, content: str) -> str:
        """Normalize content for comparison (remove trailing whitespace/newlines)."""
        return content.rstrip()
    
    async def _edit_lines(self, path: Path, line_start: int, line_end: Optional[int], 
                         old_content: str, new_content: str, encoding: str) -> Dict[str, Any]:
        """Edit (replace) lines in the file."""
        try:
            lines = await self._read_file_lines(path, encoding)
            total_lines = len(lines)
            
            # Convert to 0-indexed
            start_idx = line_start - 1
            end_idx = (line_end - 1) if line_end is not None else start_idx
            
            if start_idx >= total_lines:
                return {
                    "success": False,
                    "error": f"Line {line_start} does not exist. File has {total_lines} lines."
                }
            
            if end_idx >= total_lines:
                return {
                    "success": False,
                    "error": f"Line {end_idx + 1} does not exist. File has {total_lines} lines."
                }
            
            # Get the current content of the lines to be replaced
            if start_idx == end_idx:
                current_content = self._normalize_line_content(lines[start_idx])
            else:
                current_content = self._normalize_line_content(''.join(lines[start_idx:end_idx + 1]))
            
            # Verify old content matches
            normalized_old = self._normalize_line_content(old_content)
            if current_content != normalized_old:
                return {
                    "success": False,
                    "error": f"Content verification failed. Expected:\n'{normalized_old}'\nFound:\n'{current_content}'"
                }
            
            # Replace the lines
            new_lines = [new_content + '\n'] if not new_content.endswith('\n') and new_content else [new_content]
            if not new_content.endswith('\n') and new_content:
                new_lines = [new_content + '\n']
            elif new_content.endswith('\n'):
                new_lines = [new_content]
            else:
                new_lines = ['']  # Empty content becomes empty line
            
            # Replace the range
            lines = lines[:start_idx] + new_lines + lines[end_idx + 1:]
            
            # Write back to file
            await self._write_file_lines(path, lines, encoding)
            
            lines_affected = end_idx - start_idx + 1
            logger.info(f"Edited lines {line_start}-{line_end or line_start} in {path}")
            
            return {
                "success": True,
                "message": f"Successfully edited lines {line_start}-{line_end or line_start}",
                "file_path": self._normalize_path_for_response(path),
                "operation": "edit",
                "lines_affected": lines_affected,
                "line_start": line_start,
                "line_end": line_end or line_start,
                "new_total_lines": len(lines)
            }
            
        except UnicodeDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to decode file with encoding {encoding}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to edit file: {str(e)}"
            }
    
    async def _insert_lines(self, path: Path, line_number: int, new_content: str, encoding: str) -> Dict[str, Any]:
        """Insert lines at the specified position."""
        try:
            lines = await self._read_file_lines(path, encoding)
            total_lines = len(lines)
            
            # Convert to 0-indexed  
            insert_idx = line_number - 1
            
            # Allow inserting at end of file (line_number = total_lines + 1)
            if insert_idx > total_lines:
                return {
                    "success": False,
                    "error": f"Cannot insert at line {line_number}. File has {total_lines} lines. Maximum insert position is {total_lines + 1}."
                }
            
            # Prepare new content
            if new_content and not new_content.endswith('\n'):
                new_content += '\n'
            
            new_lines = [new_content] if new_content else ['']
            
            # Insert the lines
            lines = lines[:insert_idx] + new_lines + lines[insert_idx:]
            
            # Write back to file
            await self._write_file_lines(path, lines, encoding)
            
            logger.info(f"Inserted content at line {line_number} in {path}")
            
            return {
                "success": True,
                "message": f"Successfully inserted content at line {line_number}",
                "file_path": self._normalize_path_for_response(path),
                "operation": "insert",
                "insert_position": line_number,
                "lines_inserted": len(new_lines),
                "new_total_lines": len(lines)
            }
            
        except UnicodeDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to decode file with encoding {encoding}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to insert into file: {str(e)}"
            }
    
    async def _delete_lines(self, path: Path, line_start: int, line_end: Optional[int], 
                           old_content: str, encoding: str) -> Dict[str, Any]:
        """Delete lines from the file."""
        try:
            lines = await self._read_file_lines(path, encoding)
            total_lines = len(lines)
            
            if total_lines == 0:
                return {
                    "success": False,
                    "error": "Cannot delete from empty file"
                }
            
            # Convert to 0-indexed
            start_idx = line_start - 1
            end_idx = (line_end - 1) if line_end is not None else start_idx
            
            if start_idx >= total_lines:
                return {
                    "success": False,
                    "error": f"Line {line_start} does not exist. File has {total_lines} lines."
                }
            
            if end_idx >= total_lines:
                return {
                    "success": False,
                    "error": f"Line {end_idx + 1} does not exist. File has {total_lines} lines."
                }
            
            # Get the current content of the lines to be deleted
            if start_idx == end_idx:
                current_content = self._normalize_line_content(lines[start_idx])
            else:
                current_content = self._normalize_line_content(''.join(lines[start_idx:end_idx + 1]))
            
            # Verify old content matches
            normalized_old = self._normalize_line_content(old_content)
            if current_content != normalized_old:
                return {
                    "success": False,
                    "error": f"Content verification failed. Expected:\n'{normalized_old}'\nFound:\n'{current_content}'"
                }
            
            # Delete the lines
            lines = lines[:start_idx] + lines[end_idx + 1:]
            
            # Write back to file
            await self._write_file_lines(path, lines, encoding)
            
            lines_deleted = end_idx - start_idx + 1
            logger.info(f"Deleted lines {line_start}-{line_end or line_start} from {path}")
            
            return {
                "success": True,
                "message": f"Successfully deleted lines {line_start}-{line_end or line_start}",
                "file_path": self._normalize_path_for_response(path),
                "operation": "delete",
                "lines_deleted": lines_deleted,
                "line_start": line_start,
                "line_end": line_end or line_start,
                "new_total_lines": len(lines)
            }
            
        except UnicodeDecodeError as e:
            return {
                "success": False,
                "error": f"Failed to decode file with encoding {encoding}: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to delete from file: {str(e)}"
            }