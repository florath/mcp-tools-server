"""Security validator for file operations and path validation."""

import os
from pathlib import Path
from typing import List, Optional
from pathvalidate import validate_filename

from ..core.config import SecurityConfig


class SecurityError(Exception):
    """Security validation error."""
    pass


class SecurityValidator:
    """Validates file operations against security policies."""
    
    def __init__(self, security_config: SecurityConfig):
        self.config = security_config
        self.allowed_dir = Path(security_config.allowed_directory).resolve() if security_config.allowed_directory else None
        self.max_file_size_bytes = security_config.max_file_size_mb * 1024 * 1024
    
    def validate_file_path(self, file_path: str) -> Path:
        """Validate file path against security policies."""
        try:
            # Convert to Path and resolve (handle relative paths against allowed directory)
            path = self._resolve_path(file_path)
            
            # Check if path exists
            if not path.exists():
                raise SecurityError(f"File does not exist: {file_path}")
            
            # Check if it's a file (not directory)
            if not path.is_file():
                raise SecurityError(f"Path is not a file: {file_path}")
            
            # Check if path is within allowed directories
            if not self._is_path_allowed(path):
                raise SecurityError(f"File path not in allowed directories: {file_path}")
            
            # Check file extension
            if not self._is_extension_allowed(path):
                raise SecurityError(f"File extension not allowed: {path.suffix}")
            
            # Check file size
            if path.stat().st_size > self.max_file_size_bytes:
                raise SecurityError(f"File too large: {path.stat().st_size} bytes")
            
            return path
            
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Path validation error: {e}")
    
    def validate_directory_path(self, dir_path: str) -> Path:
        """Validate directory path against security policies."""
        try:
            # Handle relative paths by trying to resolve against allowed directories
            path = self._resolve_path(dir_path)
            
            # Check if path exists
            if not path.exists():
                raise SecurityError(f"Directory does not exist: {dir_path}")
            
            # Check if it's a directory
            if not path.is_dir():
                raise SecurityError(f"Path is not a directory: {dir_path}")
            
            # Check if path is within allowed directories
            if not self._is_path_allowed(path):
                raise SecurityError(f"Directory path not in allowed directories: {dir_path}")
            
            return path
            
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Directory validation error: {e}")
    
    def validate_filename(self, filename: str) -> str:
        """Validate filename for security."""
        try:
            validate_filename(filename)
            
            # Additional checks
            # Allow common hidden development files
            allowed_hidden_files = {
                '.gitignore', '.dockerignore', '.env', '.python-version',
                '.eslintrc', '.prettierrc', '.editorconfig', '.flake8',
                '.pylintrc', '.mypy.ini', '.coverage', '.pytest_cache'
            }
            
            if filename.startswith('.') and filename not in allowed_hidden_files:
                raise SecurityError("Hidden files not allowed")
            
            if '..' in filename:
                raise SecurityError("Path traversal not allowed")
            
            return filename
            
        except Exception as e:
            raise SecurityError(f"Filename validation error: {e}")
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within the allowed directory."""
        if not self.allowed_dir:
            return True  # No restrictions if no directory specified
        
        try:
            return path.is_relative_to(self.allowed_dir)
        except ValueError:
            # is_relative_to can raise ValueError on different filesystems
            # Fallback to string comparison for edge cases
            return str(path).startswith(str(self.allowed_dir))
        
        return False
    
    def _is_extension_allowed(self, path: Path) -> bool:
        """Check if file extension is allowed."""
        if not self.config.allowed_file_extensions:
            return True  # No restrictions if no extensions specified
        
        return path.suffix.lower() in [ext.lower() for ext in self.config.allowed_file_extensions]
    
    def validate_directory_path_for_creation(self, dir_path: str) -> Path:
        """Validate directory path for creation operations (allows non-existing paths)."""
        try:
            # Handle relative paths by trying to resolve against allowed directories
            path = self._resolve_path(dir_path)
            
            # Check if path is within allowed directories
            if not self._is_path_allowed(path):
                raise SecurityError(f"Directory path not in allowed directories: {dir_path}")
            
            return path
            
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Directory path validation error: {e}")
    
    def _resolve_path(self, path_str: str) -> Path:
        """Resolve path, handling relative paths against the allowed directory."""
        path = Path(path_str)
        
        # If it's already absolute, just resolve it
        if path.is_absolute():
            return path.resolve()
        
        # For relative paths, resolve against the allowed directory if it exists
        if self.allowed_dir:
            candidate_path = (self.allowed_dir / path).resolve()
            # Always return the candidate path when we have an allowed directory
            # The path validation will handle security checks
            return candidate_path
        
        # If no allowed directory, resolve normally (will likely fail security check)
        return path.resolve()
    
    def _is_path_allowed_raw(self, path: Path, allowed_dir: Path) -> bool:
        """Check if path is within a specific allowed directory (without looping through all)."""
        try:
            return path.is_relative_to(allowed_dir)
        except ValueError:
            # Fallback to string comparison for edge cases
            return str(path).startswith(str(allowed_dir))
    
    def get_security_info(self) -> dict:
        """Get current security configuration info."""
        return {
            "allowed_directory": str(self.allowed_dir) if self.allowed_dir else None,
            "max_file_size_mb": self.config.max_file_size_mb,
            "allowed_extensions": self.config.allowed_file_extensions
        }