"""File remover tool for deleting files with security validation."""

import asyncio
import logging
import os
import shutil
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from .base import BaseTool
from ..security.validator import SecurityError


logger = logging.getLogger(__name__)


class FileRemoverTool(BaseTool):
    """Tool for removing files with security validation and safety features."""
    
    def __init__(self, security_validator=None):
        super().__init__(
            name="file_remover",
            description="Remove files with security validation, backup options, and audit logging"
        )
        self.security_validator = security_validator
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file removal with parameters."""
        try:
            # Extract parameters
            file_path = params.get('file_path')
            force = params.get('force', False)
            create_backup = params.get('create_backup', False)
            
            if not file_path:
                raise ValueError("file_path parameter is required")
            
            # Security validation
            if self.security_validator:
                target_path = self.security_validator.validate_file_path(file_path)
            else:
                target_path = Path(file_path)
                if not target_path.exists():
                    raise ValueError(f"File does not exist: {file_path}")
                if not target_path.is_file():
                    raise ValueError(f"Path is not a file: {file_path}")
            
            logger.info(f"Removing file: {target_path}")
            
            # Get file stats before removal
            file_stats = target_path.stat()
            file_size = file_stats.st_size
            
            # Safety checks (unless force is True)
            if not force:
                await self._perform_safety_checks(target_path)
            
            backup_path = None
            # Create backup if requested
            if create_backup:
                backup_path = await self._create_backup(target_path)
            
            # Remove the file
            await self._remove_file(target_path)
            
            # Format response
            result = {
                "file_path": str(target_path),
                "size_bytes": file_size,
                "backup_created": create_backup,
                "backup_path": str(backup_path) if backup_path else None,
                "force_used": force,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully removed file: {target_path}")
            return result
            
        except SecurityError as e:
            logger.warning(f"Security error removing file: {e}")
            raise ValueError(f"Security error: {e}")
        except Exception as e:
            logger.error(f"Error removing file {params.get('file_path')}: {e}")
            raise ValueError(f"File removal error: {e}")
    
    async def _perform_safety_checks(self, file_path: Path) -> None:
        """Perform additional safety checks before removal."""
        # Check if file is read-only
        if not os.access(file_path, os.W_OK):
            raise ValueError(f"File is read-only and cannot be removed: {file_path}")
        
        # Check if file is currently open/locked (basic check)
        try:
            with open(file_path, 'r+b') as f:
                pass
        except PermissionError:
            raise ValueError(f"File appears to be in use and cannot be removed: {file_path}")
    
    async def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of the file before removal."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
        backup_path = file_path.parent / backup_name
        
        try:
            # Use asyncio to run the copy operation
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy2, str(file_path), str(backup_path))
            
            logger.info(f"Created backup: {backup_path}")
            return backup_path
            
        except Exception as e:
            raise Exception(f"Failed to create backup: {e}")
    
    async def _remove_file(self, file_path: Path) -> None:
        """Remove the file asynchronously."""
        try:
            # Use asyncio to run the removal operation
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, file_path.unlink)
            
        except Exception as e:
            raise Exception(f"Failed to remove file {file_path}: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the file remover tool."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to remove (must be within allowed directories and exist)"
                },
                "force": {
                    "type": "boolean",
                    "default": False,
                    "description": "Skip additional safety checks (default: false)"
                },
                "create_backup": {
                    "type": "boolean", 
                    "default": False,
                    "description": "Create a backup copy before removal (default: false)"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        }