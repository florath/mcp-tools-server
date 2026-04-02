"""File remover tool for deleting files with security validation."""

import asyncio
import os
import shutil
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from .base import BaseTool
from ..security.validator import SecurityError

from ..core.structured_logger import logger

class RemoveFileTool(BaseTool):
    """Tool for removing files with security validation and safety features."""
    
    def __init__(self, security_validator=None):
        super().__init__(
            name="remove_file",
            description="Remove files with security validation, backup options, and audit logging"
        )
        self.security_validator = security_validator
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file removal with parameters - idempotent operation."""
        try:
            # Extract parameters
            file_path = params.get('file_path')
            force = params.get('force', False)
            create_backup = params.get('create_backup', False)

            if not file_path:
                raise ValueError("file_path parameter is required")

            # IDEMPOTENT OPERATION: Check if file exists first
            # If it doesn't exist, return success (already deleted)
            if self.security_validator:
                try:
                    target_path = self.security_validator.validate_file_path(file_path)
                except SecurityError as e:
                    # Check if this is a "file doesn't exist" error
                    if "does not exist" in str(e).lower():
                        self.log_tool_call({"file_path": str(file_path)})
                        return {
                            "file_path": file_path,
                            "size_bytes": 0,
                            "backup_created": False,
                            "backup_path": None,
                            "force_used": force,
                            "timestamp": datetime.now().isoformat(),
                            "idempotent": True,
                            "message": "File already deleted or never existed"
                        }
                    else:
                        # Re-raise other security errors
                        raise
            else:
                target_path = Path(file_path)
                if not target_path.exists():
                    self.log_tool_call({"file_path": str(file_path)})
                    return {
                        "file_path": file_path,
                        "size_bytes": 0,
                        "backup_created": False,
                        "backup_path": None,
                        "force_used": force,
                        "timestamp": datetime.now().isoformat(),
                        "idempotent": True,
                        "message": "File already deleted or never existed"
                    }
                if not target_path.is_file():
                    raise ValueError(f"Path is not a file: {file_path}")

            self.log_tool_call(params)

            # Get file stats before removal
            file_stats = target_path.stat()
            file_size = file_stats.st_size

            # Safety checks (unless force is True)
            if not force:
                await self._perform_safety_checks(target_path, file_path)

            backup_path = None
            # Create backup if requested
            if create_backup:
                backup_path = await self._create_backup(target_path)

            # Remove the file
            await self._remove_file(target_path)

            # Format response
            result = {
                "file_path": self._normalize_path_for_response(target_path),
                "size_bytes": file_size,
                "backup_created": create_backup,
                "backup_path": self._normalize_path_for_response(backup_path) if backup_path else None,
                "force_used": force,
                "timestamp": datetime.now().isoformat(),
                "idempotent": False,
                "message": "File successfully removed"
            }

            self.log_tool_result({"success": True, "path": self._normalize_path_for_response(target_path)})
            return result

        except SecurityError as e:
            self.log_security_violation("security_error", {"error": str(e)})
            raise ValueError(f"Security error: {e}")
        except Exception as e:
            self.log_tool_error(str(e), params)
            raise ValueError(f"File removal error: {e}")
    
    async def _perform_safety_checks(self, target_path: Path, original_file_path: str) -> None:
        """Perform additional safety checks before removal."""
        # Check if file is read-only
        if not os.access(target_path, os.W_OK):
            raise ValueError(f"File is read-only and cannot be removed: {original_file_path}")
        
        # Check if file is currently open/locked (basic check)
        try:
            with open(target_path, 'r+b') as f:
                pass
        except PermissionError:
            raise ValueError(f"File appears to be in use and cannot be removed: {original_file_path}")
    
    async def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of the file before removal."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
        backup_path = file_path.parent / backup_name
        
        try:
            # Use asyncio to run the copy operation
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.copy2, str(file_path), str(backup_path))
            
            self.log_tool_result({"backup_created": str(backup_path)})
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
                    "description": "Relative path to the file to remove (e.g., 'file.txt', 'dir/file.txt')"
                }
            },
            "required": ["file_path"]
        }