"""Content searcher tool for MCP tools server."""

import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiofiles

from .base import BaseTool
from ..security.validator import SecurityValidator


logger = logging.getLogger(__name__)


class ContentSearcherTool(BaseTool):
    """Tool for searching text content within files."""
    
    def __init__(self, security_validator: SecurityValidator):
        super().__init__(
            name="content_searcher",
            description="Search for text patterns within files in allowed directories",
            security_validator=security_validator
        )
    
    def get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema for the tool."""
        return {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": "string",
                    "description": "Text or regex pattern to search for"
                },
                "search_directory": {
                    "type": "string",
                    "description": "Directory to search in (default: all allowed directories)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to search within (e.g., '*.py', '*.js')",
                    "default": "*"
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case sensitive search",
                    "default": False
                },
                "use_regex": {
                    "type": "boolean",
                    "description": "Treat search_term as regex pattern",
                    "default": False
                },
                "include_line_numbers": {
                    "type": "boolean",
                    "description": "Include line numbers in results",
                    "default": True
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines before/after match",
                    "default": 0,
                    "minimum": 0,
                    "maximum": 10
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of matches to return",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000
                },
                "max_file_size_mb": {
                    "type": "number",
                    "description": "Skip files larger than this size in MB",
                    "default": 10,
                    "minimum": 0.1,
                    "maximum": 100
                }
            },
            "required": ["search_term"]
        }

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the content searcher tool."""
        try:
            search_term = params.get('search_term')
            search_directory = params.get('search_directory')
            file_pattern = params.get('file_pattern', '*')
            case_sensitive = params.get('case_sensitive', False)
            use_regex = params.get('use_regex', False)
            include_line_numbers = params.get('include_line_numbers', True)
            context_lines = params.get('context_lines', 0)
            max_results = params.get('max_results', 100)
            max_file_size_mb = params.get('max_file_size_mb', 10)
            
            if not search_term:
                return {
                    "success": False,
                    "error": "search_term parameter is required"
                }
            
            if max_results < 1 or max_results > 1000:
                return {
                    "success": False,
                    "error": "max_results must be between 1 and 1000"
                }
            
            if context_lines < 0 or context_lines > 10:
                return {
                    "success": False,
                    "error": "context_lines must be between 0 and 10"
                }
            
            # Prepare search pattern
            try:
                if use_regex:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    pattern = re.compile(search_term, flags)
                else:
                    # For literal search, escape regex special characters
                    escaped_term = re.escape(search_term)
                    flags = 0 if case_sensitive else re.IGNORECASE
                    pattern = re.compile(escaped_term, flags)
            except re.error as e:
                return {
                    "success": False,
                    "error": f"Invalid regex pattern: {str(e)}"
                }
            
            # Determine search directories
            search_paths = []
            if search_directory:
                try:
                    search_path = self.security_validator.validate_directory_path_for_creation(search_directory)
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
                # Use the allowed directory
                allowed_dir = self.security_validator.allowed_dir
                if not allowed_dir:
                    return {
                        "success": False,
                        "error": "No allowed directory configured and no search_directory specified"
                    }
                if allowed_dir.exists() and allowed_dir.is_dir():
                    search_paths = [allowed_dir]
                else:
                    search_paths = []
            
            # Search for content
            results = await self._search_content(
                search_paths, pattern, file_pattern, include_line_numbers, 
                context_lines, max_results, max_file_size_mb
            )
            
            return {
                "success": True,
                "search_term": search_term,
                "search_directories": [self._normalize_path_for_response(p) for p in search_paths],
                "file_pattern": file_pattern,
                "case_sensitive": case_sensitive,
                "use_regex": use_regex,
                "total_matches": sum(len(r["matches"]) for r in results),
                "files_searched": len([r for r in results if r.get("searched", True)]),
                "files_with_matches": len([r for r in results if r["matches"]]),
                "max_results": max_results,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error in content_searcher tool: {e}")
            return {
                "success": False,
                "error": f"Internal error: {str(e)}"
            }
    
    async def _search_content(
        self,
        search_paths: List[Path],
        pattern: re.Pattern,
        file_pattern: str,
        include_line_numbers: bool,
        context_lines: int,
        max_results: int,
        max_file_size_mb: float
    ) -> List[Dict[str, Any]]:
        """Search for content in files."""
        results = []
        total_matches = 0
        max_file_size_bytes = max_file_size_mb * 1024 * 1024
        
        for search_path in search_paths:
            try:
                # Find files matching the pattern
                files = list(search_path.rglob(file_pattern))
                
                for file_path in files:
                    if total_matches >= max_results:
                        break
                    
                    # Skip if not a file
                    if not file_path.is_file():
                        continue
                    
                    # Skip if file is too large
                    try:
                        file_size = file_path.stat().st_size
                        if file_size > max_file_size_bytes:
                            results.append({
                                "file_path": self._normalize_path_for_response(file_path),
                                "relative_path": str(file_path.relative_to(search_path)),
                                "matches": [],
                                "error": f"File too large ({file_size / (1024*1024):.1f}MB, max: {max_file_size_mb}MB)",
                                "searched": False
                            })
                            continue
                    except OSError:
                        continue
                    
                    # Skip if file extension not allowed
                    try:
                        if not self.security_validator._is_extension_allowed(file_path):
                            continue
                    except:
                        continue
                    
                    # Search within the file
                    file_matches = await self._search_in_file(
                        file_path, search_path, pattern, include_line_numbers, 
                        context_lines, max_results - total_matches
                    )
                    
                    if file_matches is not None:
                        results.append(file_matches)
                        total_matches += len(file_matches["matches"])
                
                # Break if we've reached max results
                if total_matches >= max_results:
                    break
                    
            except PermissionError as e:
                logger.warning(f"Permission denied accessing {search_path}: {e}")
                continue
            except Exception as e:
                logger.error(f"Error searching in {search_path}: {e}")
                continue
        
        return results
    
    async def _search_in_file(
        self,
        file_path: Path,
        base_path: Path,
        pattern: re.Pattern,
        include_line_numbers: bool,
        context_lines: int,
        max_matches: int
    ) -> Optional[Dict[str, Any]]:
        """Search for pattern within a single file."""
        matches = []
        
        try:
            # Try reading with UTF-8 first, fallback to latin-1
            content = None
            encoding_used = "utf-8"
            
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            except UnicodeDecodeError:
                try:
                    async with aiofiles.open(file_path, 'r', encoding='latin-1') as f:
                        content = await f.read()
                        encoding_used = "latin-1"
                except Exception:
                    return {
                        "file_path": self._normalize_path_for_response(file_path),
                        "relative_path": str(file_path.relative_to(base_path)),
                        "matches": [],
                        "error": "Could not read file (encoding issues)",
                        "searched": False
                    }
            
            if content is None:
                return None
            
            lines = content.splitlines()
            
            for line_num, line in enumerate(lines, 1):
                if len(matches) >= max_matches:
                    break
                
                match = pattern.search(line)
                if match:
                    match_info = {
                        "line_content": line.strip(),
                        "match_start": match.start(),
                        "match_end": match.end(),
                        "matched_text": match.group()
                    }
                    
                    if include_line_numbers:
                        match_info["line_number"] = line_num
                    
                    # Add context lines if requested
                    if context_lines > 0:
                        start_line = max(0, line_num - context_lines - 1)
                        end_line = min(len(lines), line_num + context_lines)
                        
                        context_before = []
                        context_after = []
                        
                        for i in range(start_line, line_num - 1):
                            context_before.append({
                                "line_number": i + 1,
                                "content": lines[i].strip()
                            })
                        
                        for i in range(line_num, end_line):
                            context_after.append({
                                "line_number": i + 1,
                                "content": lines[i].strip()
                            })
                        
                        match_info["context_before"] = context_before
                        match_info["context_after"] = context_after
                    
                    matches.append(match_info)
            
            return {
                "file_path": self._normalize_path_for_response(file_path),
                "relative_path": str(file_path.relative_to(base_path)),
                "matches": matches,
                "encoding": encoding_used,
                "searched": True
            }
            
        except PermissionError:
            return {
                "file_path": self._normalize_path_for_response(file_path),
                "relative_path": str(file_path.relative_to(base_path)),
                "matches": [],
                "error": "Permission denied",
                "searched": False
            }
        except Exception as e:
            logger.error(f"Error searching in file {file_path}: {e}")
            return {
                "file_path": self._normalize_path_for_response(file_path),
                "relative_path": str(file_path.relative_to(base_path)),
                "matches": [],
                "error": str(e),
                "searched": False
            }