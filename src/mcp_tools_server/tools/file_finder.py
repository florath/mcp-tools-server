"""File finder tool for MCP tools server."""

import asyncio
import fnmatch
import logging
from pathlib import Path
from typing import Dict, Any, List

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class FileFinderTool(BaseTool):
    """Tool for finding files and directories by name patterns."""
    
    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="file_finder",
            description="Find files and directories by name patterns within allowed directories",
            security_validator=security_validator
        )
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Pattern to search for (supports wildcards like *.py, test_*, etc.)"
                },
                "search_directory": {
                    "type": "string",
                    "description": "Directory to search in (default: all allowed directories)"
                },
                "file_type": {
                    "type": "string",
                    "description": "Type of items to find: 'files', 'directories', or 'both'",
                    "enum": ["files", "directories", "both"],
                    "default": "both"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search recursively in subdirectories",
                    "default": True
                },
                "case_sensitive": {
                    "type": "boolean", 
                    "description": "Case sensitive pattern matching",
                    "default": False
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000
                }
            },
            "required": ["pattern"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the file finder tool."""
        try:
            pattern = params.get('pattern')
            search_directory = params.get('search_directory')
            file_type = params.get('file_type', 'both')
            recursive = params.get('recursive', True)
            case_sensitive = params.get('case_sensitive', False)
            max_results = params.get('max_results', 100)
            
            if not pattern:
                return {
                    "success": False,
                    "error": "pattern parameter is required"
                }
            
            if max_results < 1 or max_results > 1000:
                return {
                    "success": False,
                    "error": "max_results must be between 1 and 1000"
                }
            
            # Determine search directories
            search_paths = []
            if search_directory:
                # Validate the specific directory
                try:
                    self.security_validator.validate_directory_path_for_creation(search_directory)
                    search_path = Path(search_directory).resolve()
                    if search_path.exists() and search_path.is_dir():
                        search_paths.append(search_path)
                    else:
                        return {
                            "success": False,
                            "error": f"Search directory does not exist or is not a directory: {search_directory}"
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Security validation failed for search directory: {str(e)}"
                    }
            else:
                # Use all allowed directories
                allowed_dirs = self.security_validator.allowed_dirs
                if not allowed_dirs:
                    return {
                        "success": False,
                        "error": "No allowed directories configured and no search_directory specified"
                    }
                search_paths = [d for d in allowed_dirs if d.exists() and d.is_dir()]
            
            # Search for files
            results = await self._search_files(
                search_paths, pattern, file_type, recursive, case_sensitive, max_results
            )
            
            return {
                "success": True,
                "pattern": pattern,
                "search_directories": [str(p) for p in search_paths],
                "file_type": file_type,
                "recursive": recursive,
                "case_sensitive": case_sensitive,
                "total_found": len(results),
                "max_results": max_results,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error in file_finder tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def _search_files(
        self, 
        search_paths: List[Path], 
        pattern: str, 
        file_type: str, 
        recursive: bool, 
        case_sensitive: bool,
        max_results: int
    ) -> List[Dict[str, Any]]:
        """Search for files matching the pattern."""
        results = []
        
        # Normalize pattern for case insensitive search
        search_pattern = pattern if case_sensitive else pattern.lower()
        
        for search_path in search_paths:
            try:
                if recursive:
                    # Use rglob for recursive search
                    items = search_path.rglob("*")
                else:
                    # Use glob for non-recursive search
                    items = search_path.glob("*")
                
                for item in items:
                    if len(results) >= max_results:
                        break
                    
                    # Skip if wrong type
                    if file_type == "files" and not item.is_file():
                        continue
                    elif file_type == "directories" and not item.is_dir():
                        continue
                    
                    # Check pattern match
                    item_name = item.name if case_sensitive else item.name.lower()
                    if fnmatch.fnmatch(item_name, search_pattern):
                        try:
                            stat = item.stat()
                            result = {
                                "path": str(item),
                                "name": item.name,
                                "type": "directory" if item.is_dir() else "file",
                                "size": stat.st_size if item.is_file() else None,
                                "parent_directory": str(item.parent),
                                "relative_path": str(item.relative_to(search_path))
                            }
                            results.append(result)
                        except (OSError, PermissionError) as e:
                            logger.warning(f"Error accessing {item}: {e}")
                            continue
                
                # Break if we've reached max results across all search paths
                if len(results) >= max_results:
                    break
                    
            except PermissionError as e:
                logger.warning(f"Permission denied accessing {search_path}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error searching in {search_path}: {e}")
                continue
        
        # Sort results by path for consistent output
        results.sort(key=lambda x: x["path"])
        
        return results