"""Directory manager tool for MCP tools server."""

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class DirectoryManagerTool(BaseTool):
    """Tool for managing directories - create, remove, and list operations."""
    
    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="directory_manager",
            description="Create, remove, and list directories with security validation",
            security_validator=security_validator
        )
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "Operation to perform: 'create', 'remove', or 'list'",
                    "enum": ["create", "remove", "list"]
                },
                "directory_path": {
                    "type": "string", 
                    "description": "Path to the directory"
                },
                "create_parents": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist (create operation only)",
                    "default": True
                },
                "force_remove": {
                    "type": "boolean",
                    "description": "Force remove non-empty directories (remove operation only)",
                    "default": False
                }
            },
            "required": ["operation", "directory_path"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the directory manager tool."""
        try:
            operation = params.get('operation')
            directory_path = params.get('directory_path')
            create_parents = params.get('create_parents', True)
            force_remove = params.get('force_remove', False)
            
            if not operation:
                return {
                    "success": False,
                    "error": "operation parameter is required"
                }
                
            if not directory_path:
                return {
                    "success": False,
                    "error": "directory_path parameter is required"
                }
            
            # Security validation and path resolution
            try:
                if operation == "create":
                    path = self.security_validator.validate_directory_path_for_creation(directory_path)
                else:
                    path = self.security_validator.validate_directory_path(directory_path)
            except (ValueError, Exception) as e:
                return {
                    "success": False,
                    "error": f"Security validation failed: {str(e)}"
                }
            
            if operation == "create":
                return await self._create_directory(path, create_parents)
            elif operation == "remove":
                return await self._remove_directory(path, force_remove)
            elif operation == "list":
                return await self._list_directory(path)
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}. Must be 'create', 'remove', or 'list'"
                }
                
        except Exception as e:
            logger.error(f"Error in directory_manager tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def _create_directory(self, path: Path, create_parents: bool) -> Dict[str, Any]:
        """Create a directory."""
        try:
            if path.exists():
                if path.is_dir():
                    return {
                        "success": True,
                        "message": f"Directory already exists: {path}",
                        "directory_path": str(path),
                        "operation": "create",
                        "already_existed": True
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Path exists but is not a directory: {path}"
                    }
            
            # Create the directory
            if create_parents:
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory with parents: {path}")
            else:
                path.mkdir(exist_ok=False)
                logger.info(f"Created directory: {path}")
            
            return {
                "success": True,
                "message": f"Successfully created directory: {path}",
                "directory_path": str(path),
                "operation": "create",
                "already_existed": False,
                "created_parents": create_parents
            }
            
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied creating directory: {path}"
            }
        except FileExistsError:
            return {
                "success": False,
                "error": f"Parent directory does not exist and create_parents is False: {path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create directory: {str(e)}"
            }
    
    async def _remove_directory(self, path: Path, force_remove: bool) -> Dict[str, Any]:
        """Remove a directory."""
        try:
            if not path.exists():
                return {
                    "success": True,
                    "message": f"Directory does not exist (already removed): {path}",
                    "directory_path": str(path),
                    "operation": "remove",
                    "was_removed": False
                }
            
            if not path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {path}"
                }
            
            # Check if directory is empty
            try:
                contents = list(path.iterdir())
                is_empty = len(contents) == 0
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied accessing directory: {path}"
                }
            
            if not is_empty and not force_remove:
                return {
                    "success": False,
                    "error": f"Directory is not empty. Use force_remove=true to remove non-empty directories: {path}",
                    "contents_count": len(contents)
                }
            
            # Remove the directory
            if force_remove and not is_empty:
                shutil.rmtree(path)
                logger.info(f"Force removed non-empty directory: {path}")
            else:
                path.rmdir()
                logger.info(f"Removed empty directory: {path}")
            
            return {
                "success": True,
                "message": f"Successfully removed directory: {path}",
                "directory_path": str(path),
                "operation": "remove",
                "was_removed": True,
                "was_empty": is_empty
            }
            
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied removing directory: {path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to remove directory: {str(e)}"
            }
    
    async def _list_directory(self, path: Path) -> Dict[str, Any]:
        """List directory contents."""
        try:
            if not path.exists():
                return {
                    "success": False,
                    "error": f"Directory does not exist: {path}"
                }
            
            if not path.is_dir():
                return {
                    "success": False,
                    "error": f"Path is not a directory: {path}"
                }
            
            # List contents
            contents = []
            try:
                for item in path.iterdir():
                    item_info = {
                        "name": item.name,
                        "path": str(item),
                        "type": "directory" if item.is_dir() else "file",
                        "size": item.stat().st_size if item.is_file() else None
                    }
                    contents.append(item_info)
            except PermissionError:
                return {
                    "success": False,
                    "error": f"Permission denied listing directory: {path}"
                }
            
            # Sort by type (directories first), then by name
            contents.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
            
            return {
                "success": True,
                "message": f"Successfully listed directory: {path}",
                "directory_path": str(path),
                "operation": "list",
                "contents": contents,
                "total_items": len(contents),
                "directories": len([c for c in contents if c["type"] == "directory"]),
                "files": len([c for c in contents if c["type"] == "file"])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to list directory: {str(e)}"
            }