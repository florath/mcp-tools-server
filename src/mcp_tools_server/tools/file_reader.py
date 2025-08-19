"""File reader tool for reading files with security validation."""

import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import aiofiles

from .base import BaseTool
from ..security.validator import SecurityError


logger = logging.getLogger(__name__)


class FileReaderTool(BaseTool):
    """Tool for reading files with security validation."""
    
    def __init__(self, security_validator=None, max_files_per_request: int = 10):
        super().__init__(
            name="file_reader",
            description="Read files with security validation and path restrictions"
        )
        self.security_validator = security_validator
        self.max_files_per_request = max_files_per_request
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file reading with parameters."""
        try:
            # Extract parameters
            file_path = params.get('file_path')
            encoding = params.get('encoding', 'utf-8')
            include_line_numbers = params.get('include_line_numbers', False)
            
            if not file_path:
                raise ValueError("file_path parameter is required")
            
            # Validate file path
            if self.security_validator:
                validated_path = self.security_validator.validate_file_path(file_path)
            else:
                validated_path = Path(file_path)
            
            logger.info(f"Reading file: {validated_path}")
            
            # Read file content
            content = await self._read_file(validated_path, encoding)
            
            # Format response
            result = {
                "file_path": str(validated_path),
                "encoding": encoding,
                "size_bytes": validated_path.stat().st_size,
                "content": content
            }
            
            # Add line numbers if requested
            if include_line_numbers:
                lines = content.split('\n')
                numbered_lines = [f"{i+1:4d}: {line}" for i, line in enumerate(lines)]
                result["content_with_line_numbers"] = '\n'.join(numbered_lines)
            
            return result
            
        except SecurityError as e:
            logger.warning(f"Security error reading file: {e}")
            raise ValueError(f"Security error: {e}")
        except Exception as e:
            logger.error(f"Error reading file {params.get('file_path')}: {e}")
            raise ValueError(f"File reading error: {e}")
    
    async def _read_file(self, file_path: Path, encoding: str) -> str:
        """Read file content asynchronously."""
        try:
            async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                content = await f.read()
            return content
        except UnicodeDecodeError as e:
            # Try with fallback encoding
            logger.warning(f"Failed to read with {encoding}, trying latin-1: {e}")
            async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                content = await f.read()
            return content
        except Exception as e:
            raise Exception(f"Failed to read file {file_path}: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the file reader tool."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read (must be within allowed directories)"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding (default: utf-8)"
                },
                "include_line_numbers": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include line numbers in the response (default: false)"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        }