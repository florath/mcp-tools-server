"""Security validator for file operations and path validation."""

import logging
import os
from pathlib import Path
from typing import List, Optional
from pathvalidate import validate_filename

from ..core.config import SecurityConfig


logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Security validation error."""
    pass


class SecurityValidator:
    """Validates file operations against security policies."""
    
    def __init__(self, security_config: SecurityConfig):
        self.config = security_config
        self.allowed_dir = Path(security_config.allowed_directory).resolve() if security_config.allowed_directory else None
        self.max_file_size_bytes = security_config.max_file_size_mb * 1024 * 1024
        self._session_directory: Optional[Path] = None
    
    def set_session_directory(self, session_directory: Optional[Path]) -> None:
        """Set session directory for current request context."""
        self._session_directory = session_directory
    
    def get_effective_base_directory(self) -> Optional[Path]:
        """Get the effective base directory (session dir if available, otherwise allowed dir)."""
        return self._session_directory or self.allowed_dir
    
    def validate_file_path(self, file_path: str) -> Path:
        """Validate file path against security policies."""
        try:
            # Convert to Path and resolve (handle relative paths against allowed directory)
            path = self._resolve_path(file_path)
            
            # Check if path exists
            if not path.exists():
                logger.warning(f"File '{file_path}' does not exist{self._get_context_info()}{self._get_available_directories_info()}")
                raise SecurityError(f"File '{file_path}' does not exist")
            
            # Check if it's a file (not directory)
            if not path.is_file():
                logger.warning(f"Path '{file_path}' is not a file{self._get_context_info()}")
                raise SecurityError(f"Path '{file_path}' is not a file")
            
            # Check if path is within allowed directories
            if not self._is_path_allowed(path):
                logger.warning(f"File '{file_path}' is not in allowed directories{self._get_context_info()}")
                raise SecurityError(f"File '{file_path}' is not in allowed directories")
            
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
                logger.warning(f"Directory '{dir_path}' does not exist{self._get_context_info()}{self._get_available_directories_info()}")
                raise SecurityError(f"Directory '{dir_path}' does not exist")
            
            # Check if it's a directory
            if not path.is_dir():
                logger.warning(f"Path '{dir_path}' is not a directory{self._get_context_info()}")
                raise SecurityError(f"Path '{dir_path}' is not a directory")
            
            # Check if path is within allowed directories
            if not self._is_path_allowed(path):
                logger.warning(f"Directory '{dir_path}' is not in allowed directories{self._get_context_info()}")
                raise SecurityError(f"Directory '{dir_path}' is not in allowed directories")
            
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
        """Check if path is within the effective base directory."""
        # CRITICAL: When session is active, ONLY allow paths within session directory
        # This enforces strict session boundary isolation
        if self._session_directory:
            try:
                return path.is_relative_to(self._session_directory)
            except ValueError:
                # Fallback to string comparison for edge cases
                return str(path).startswith(str(self._session_directory))
        
        # If no session, fall back to allowed directory check
        base_dir = self.get_effective_base_directory()
        if not base_dir:
            return True  # No restrictions if no directory specified
        
        try:
            return path.is_relative_to(base_dir)
        except ValueError:
            # is_relative_to can raise ValueError on different filesystems
            # Fallback to string comparison for edge cases
            return str(path).startswith(str(base_dir))
        
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
                logger.warning(f"Directory '{dir_path}' is not in allowed directories{self._get_context_info()}")
                raise SecurityError(f"Directory '{dir_path}' is not in allowed directories")
            
            return path
            
        except Exception as e:
            if isinstance(e, SecurityError):
                raise
            raise SecurityError(f"Directory path validation error: {e}")
    
    def _resolve_path(self, path_str: str) -> Path:
        """Resolve path, handling relative paths against the effective base directory."""
        path = Path(path_str)
        
        # SECURITY: Reject absolute paths to enforce session isolation
        # This prevents tools from accessing files outside the session directory
        if path.is_absolute():
            raise SecurityError(
                "Absolute paths are not allowed for security reasons. Use relative paths only."
            )
        
        # For relative paths, resolve against the effective base directory
        base_dir = self.get_effective_base_directory()
        if base_dir:
            candidate_path = (base_dir / path).resolve()
            
            
            # CRITICAL FIX: Ensure the resolved path is still within the session directory
            # This prevents directory creation outside the session when using parents=True
            if self._session_directory:
                try:
                    if not candidate_path.is_relative_to(self._session_directory):
                        raise SecurityError(
                            "Resolved path would be outside session directory"
                        )
                except ValueError:
                    # Fallback for different filesystems
                    if not str(candidate_path).startswith(str(self._session_directory)):
                        raise SecurityError(
                            "Resolved path would be outside session directory"
                        )
            
            return candidate_path
        
        # If no base directory, we can't resolve relative paths safely
        raise SecurityError("No session directory available to resolve relative path")
    
    def _is_path_allowed_raw(self, path: Path, allowed_dir: Path) -> bool:
        """Check if path is within a specific allowed directory (without looping through all)."""
        try:
            return path.is_relative_to(allowed_dir)
        except ValueError:
            # Fallback to string comparison for edge cases
            return str(path).startswith(str(allowed_dir))
    
    def get_security_info(self) -> dict:
        """Get current security configuration info."""
        base_dir = self.get_effective_base_directory()
        return {
            "allowed_directory": str(self.allowed_dir) if self.allowed_dir else None,
            "session_directory": str(self._session_directory) if self._session_directory else None,
            "effective_base_directory": str(base_dir) if base_dir else None,
            "max_file_size_mb": self.config.max_file_size_mb,
            "allowed_extensions": self.config.allowed_file_extensions
        }
    
    def _get_context_info(self) -> str:
        """Get context information for error messages."""
        base_dir = self.get_effective_base_directory()
        if base_dir:
            # Only show the last part of the path to avoid exposing absolute paths
            dir_name = base_dir.name
            return f" in session directory '{dir_name}'"
        return ""
    
    def _get_available_directories_info(self) -> str:
        """Get information about available directories for error messages."""
        # Removed confusing directory listing - not helpful for users
        return ""