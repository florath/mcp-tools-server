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
        self.allowed_dirs = [Path(d).resolve() for d in security_config.allowed_directories]
        self.max_file_size_bytes = security_config.max_file_size_mb * 1024 * 1024
    
    def validate_file_path(self, file_path: str) -> Path:
        """Validate file path against security policies."""
        try:
            # Convert to Path and resolve
            path = Path(file_path).resolve()
            
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
            # Convert to Path and resolve
            path = Path(dir_path).resolve()
            
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
            if filename.startswith('.'):
                raise SecurityError("Hidden files not allowed")
            
            if '..' in filename:
                raise SecurityError("Path traversal not allowed")
            
            return filename
            
        except Exception as e:
            raise SecurityError(f"Filename validation error: {e}")
    
    def _is_path_allowed(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        if not self.allowed_dirs:
            return True  # No restrictions if no directories specified
        
        try:
            for allowed_dir in self.allowed_dirs:
                if path.is_relative_to(allowed_dir):
                    return True
        except ValueError:
            # is_relative_to can raise ValueError on different filesystems
            pass
        
        # Fallback to string comparison for edge cases
        path_str = str(path)
        for allowed_dir in self.allowed_dirs:
            if path_str.startswith(str(allowed_dir)):
                return True
        
        return False
    
    def _is_extension_allowed(self, path: Path) -> bool:
        """Check if file extension is allowed."""
        if not self.config.allowed_file_extensions:
            return True  # No restrictions if no extensions specified
        
        return path.suffix.lower() in [ext.lower() for ext in self.config.allowed_file_extensions]
    
    def validate_directory_path_for_creation(self, dir_path: str) -> Path:
        """Validate directory path for creation operations (allows non-existing paths)."""
        try:
            # Convert to Path and resolve
            path = Path(dir_path).resolve()
            
            # Check if path is within allowed directories
            if not self._is_path_allowed(path):
                raise SecurityError(f"Directory path not in allowed directories: {dir_path}")
            
            return path
            
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Directory path validation error: {e}")
    
    def get_security_info(self) -> dict:
        """Get current security configuration info."""
        return {
            "allowed_directories": [str(d) for d in self.allowed_dirs],
            "max_file_size_mb": self.config.max_file_size_mb,
            "allowed_extensions": self.config.allowed_file_extensions
        }