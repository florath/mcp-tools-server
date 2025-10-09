"""File mover tool for moving/renaming files with security validation."""

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


class FileMoverTool(BaseTool):
    """Tool for moving/renaming files with security validation and safety features."""
    
    def __init__(self, security_validator=None):
        super().__init__(
            name="file_mover",
            description="Move or rename files with security validation, backup options, and audit logging"
        )
        self.security_validator = security_validator
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute file move/rename with parameters."""
        try:
            # Extract parameters
            source_path = params.get('source_path')
            destination_path = params.get('destination_path')
            overwrite = params.get('overwrite', False)
            create_backup = params.get('create_backup', False)
            
            if not source_path:
                raise ValueError("source_path parameter is required")
            if not destination_path:
                raise ValueError("destination_path parameter is required")
            
            # Security validation
            if self.security_validator:
                validated_source = self.security_validator.validate_file_path(source_path)
                
                # For destination, use _resolve_path and validate parent directory
                validated_dest = self.security_validator._resolve_path(destination_path)
                
                # Validate the parent directory is allowed (for creation)
                parent_dir = validated_dest.parent
                original_parent = str(Path(destination_path).parent)
                if original_parent and original_parent != '.':
                    self.security_validator.validate_directory_path_for_creation(original_parent)
                
                # Validate filename
                self.security_validator.validate_filename(validated_dest.name)
            else:
                validated_source = Path(source_path)
                validated_dest = Path(destination_path)
                
                if not validated_source.exists():
                    raise ValueError(f"Source file does not exist: {source_path}")
                if not validated_source.is_file():
                    raise ValueError(f"Source path is not a file: {source_path}")
            
            logger.info(f"Moving file from {validated_source} to {validated_dest}")
            
            # Get file stats before moving
            source_stats = validated_source.stat()
            file_size = source_stats.st_size
            
            # Check if destination already exists
            dest_exists = validated_dest.exists()
            if dest_exists and not overwrite:
                raise ValueError(f"Destination file already exists. Use overwrite=true to replace: {destination_path}")
            
            backup_path = None
            # Create backup if destination exists and backup is requested
            if dest_exists and create_backup and overwrite:
                backup_path = await self._create_backup(validated_dest)
            
            # Create destination directory if it doesn't exist
            validated_dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Perform the move operation
            await self._move_file(validated_source, validated_dest)
            
            # Format response
            result = {
                "source_path": self._normalize_path_for_response(validated_source),
                "destination_path": self._normalize_path_for_response(validated_dest),
                "size_bytes": file_size,
                "overwrite_used": overwrite and dest_exists,
                "backup_created": backup_path is not None,
                "backup_path": self._normalize_path_for_response(backup_path) if backup_path else None,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully moved file from {validated_source} to {validated_dest}")
            return result
            
        except SecurityError as e:
            logger.warning(f"Security error moving file: {e}")
            raise ValueError(f"Security error: {e}")
        except Exception as e:
            logger.error(f"Error moving file from {params.get('source_path')} to {params.get('destination_path')}: {e}")
            raise ValueError(f"File move error: {e}")
    
    async def _create_backup(self, file_path: Path) -> Path:
        """Create a backup of the destination file before overwriting."""
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
    
    async def _move_file(self, source_path: Path, destination_path: Path) -> None:
        """Move the file asynchronously."""
        try:
            # Use asyncio to run the move operation
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.move, str(source_path), str(destination_path))
            
        except Exception as e:
            raise Exception(f"Failed to move file from {source_path} to {destination_path}: {e}")
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the file mover tool."""
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Path to the source file to move or rename"
                },
                "destination_path": {
                    "type": "string",
                    "description": "Path where the file should be moved to"
                }
            },
            "required": ["source_path", "destination_path"]
        }