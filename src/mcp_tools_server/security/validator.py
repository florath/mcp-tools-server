"""Security validator for file operations and path validation."""

import os
from contextvars import ContextVar, Token
from pathlib import Path
from typing import List, Optional
from pathvalidate import validate_filename

from ..core.config import SecurityConfig


from ..core.structured_logger import logger

# Per-async-task context variable for the active session directory.
# Using ContextVar makes concurrent requests safe: each asyncio task
# (i.e. each HTTP request) has its own independent copy of this value.
_session_directory_ctx: ContextVar[Optional[Path]] = ContextVar(
    "mcp_session_directory", default=None
)


class SecurityError(Exception):
    """Security validation error."""
    pass


class SecurityValidator:
    """Validates file operations against security policies."""

    def __init__(self, security_config: SecurityConfig):
        self.config = security_config
        self.max_file_size_bytes = security_config.max_file_size_mb * 1024 * 1024

    def set_session_directory(self, session_directory: Optional[Path]) -> Token:
        """Set session directory for the current async context.

        Returns the ContextVar Token so the caller can reset it via
        ``reset_session_directory(token)`` in a finally block.
        """
        return _session_directory_ctx.set(session_directory)

    def reset_session_directory(self, token: Token) -> None:
        """Restore the session directory to its previous value."""
        _session_directory_ctx.reset(token)

    def get_effective_base_directory(self) -> Path:
        """Get the effective base directory for the current session."""
        session_dir = _session_directory_ctx.get()
        if session_dir:
            return session_dir
        raise SecurityError("No active session. All operations require a valid session.")
    
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
        """Check if path is within the active session directory."""
        session_dir = _session_directory_ctx.get()
        if session_dir:
            try:
                return path.is_relative_to(session_dir)
            except ValueError:
                return str(path).startswith(str(session_dir))
        raise SecurityError("No active session. All operations require a valid session.")
    
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
        """Resolve path, handling both absolute and relative paths."""
        path = Path(path_str)

        # Check if we have session directory or allowed directory
        base_dir = _session_directory_ctx.get()
        if not base_dir:
            raise SecurityError("No active session or allowed directory. All operations require a valid session directory or allowed directory configuration.")

        # Handle absolute paths - only allow if within allowed directory
        if path.is_absolute():
            try:
                if not path.is_relative_to(base_dir):
                    raise SecurityError(f"Absolute path '{path}' is outside the allowed directory '{base_dir}'")
                return path.resolve()
            except ValueError:
                # Fallback for different filesystems
                if not str(path).startswith(str(base_dir)):
                    raise SecurityError(f"Absolute path '{path}' is outside the allowed directory '{base_dir}'")
                return path.resolve()

        # For relative paths, resolve against the base directory (session or allowed)
        candidate_path = (base_dir / path).resolve()

        # Ensure the resolved path is still within the base directory
        try:
            if not candidate_path.is_relative_to(base_dir):
                raise SecurityError(
                    f"Resolved path would be outside the base directory '{base_dir}'"
                )
        except ValueError:
            # Fallback for different filesystems
            if not str(candidate_path).startswith(str(base_dir)):
                raise SecurityError(
                    f"Resolved path would be outside the base directory '{base_dir}'"
                )

        return candidate_path
    
    def get_security_info(self) -> dict:
        """Get current security configuration info."""
        session_dir = _session_directory_ctx.get()
        return {
            "session_directory": str(session_dir) if session_dir else None,
            "max_file_size_mb": self.config.max_file_size_mb,
            "allowed_extensions": self.config.allowed_file_extensions,
        }
    
    def _get_context_info(self) -> str:
        """Get context information for error messages."""
        session_dir = _session_directory_ctx.get()
        return f" in session directory '{session_dir.name}'" if session_dir else " (no active session)"
    
    def _get_available_directories_info(self) -> str:
        """Get information about available directories for error messages."""
        # Removed confusing directory listing - not helpful for users
        return ""