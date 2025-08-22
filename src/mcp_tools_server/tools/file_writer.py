"""File writer tool for creating and writing files with security validation."""

import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import aiofiles

from .base import BaseTool
from ..security.validator import SecurityError


logger = logging.getLogger(__name__)


class FileWriterTool(BaseTool):
    """Tool for writing files with security validation."""
    
    def __init__(self, security_validator=None):
        super().__init__(
            name="file_writer",
            description="Create or overwrite files with specified content and security validation"
        )
        self.security_validator = security_validator
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file writing with parameters."""
        try:
            # Extract parameters
            file_path = params.get('file_path')
            content = params.get('content', '')
            encoding = params.get('encoding', 'utf-8')
            create_dirs = params.get('create_dirs', True)
            
            if not file_path:
                raise ValueError("file_path parameter is required")
            
            # Convert to Path object and resolve relative paths
            if self.security_validator:
                # Use security validator to resolve path (handles relative paths)
                target_path = self.security_validator._resolve_path(file_path)
                
                # Validate the parent directory is allowed (for creation)
                parent_dir = target_path.parent
                self.security_validator.validate_directory_path_for_creation(str(parent_dir))
                
                # Validate filename
                self.security_validator.validate_filename(target_path.name)
                
                # Check file extension is allowed
                if target_path.suffix and not self._is_extension_allowed(target_path):
                    raise SecurityError(f"File extension not allowed: {target_path.suffix}")
            else:
                target_path = Path(file_path)
            
            logger.info(f"Writing file: {target_path}")
            
            # Create parent directories if needed and allowed
            if create_dirs and not parent_dir.exists():
                logger.info(f"Creating parent directories: {parent_dir}")
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            # Write file content
            await self._write_file(target_path, content, encoding)
            
            # Get file stats after writing
            file_stats = target_path.stat()
            
            # Format response
            result = {
                "file_path": str(target_path),
                "content_length": len(content),
                "encoding": encoding,
                "size_bytes": file_stats.st_size,
                "created_directories": create_dirs and not target_path.parent.exists(),
                "operation": "created" if not target_path.exists() else "overwritten"
            }
            
            return result
            
        except SecurityError as e:
            logger.warning(f"Security error writing file: {e}")
            raise ValueError(f"Security error: {e}")
        except Exception as e:
            logger.error(f"Error writing file {params.get('file_path')}: {e}")
            raise ValueError(f"File writing error: {e}")
    
    async def _write_file(self, file_path: Path, content: str, encoding: str) -> None:
        """Write file content asynchronously."""
        try:
            async with aiofiles.open(file_path, 'w', encoding=encoding) as f:
                await f.write(content)
        except Exception as e:
            raise Exception(f"Failed to write file {file_path}: {e}")
    
    def _is_extension_allowed(self, file_path: Path) -> bool:
        """Check if file extension is allowed."""
        if not self.security_validator:
            return True
        
        # Use the security validator's extension check
        try:
            allowed_extensions = self.security_validator.config.allowed_file_extensions
            if not allowed_extensions:
                return True  # No restrictions
            return file_path.suffix.lower() in [ext.lower() for ext in allowed_extensions]
        except:
            return True  # Default to allow if check fails
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the file writer tool."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to create or overwrite (must be within allowed directories)"
                },
                "content": {
                    "type": "string",
                    "default": "",
                    "description": "Content to write to the file (default: empty string)"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "File encoding (default: utf-8)"
                },
                "create_dirs": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create parent directories if they don't exist (default: true)"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        }