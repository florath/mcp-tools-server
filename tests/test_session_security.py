"""Tests for session-aware SecurityValidator functionality."""

import pytest
import tempfile
from pathlib import Path

from src.mcp_tools_server.core.config import SecurityConfig
from src.mcp_tools_server.security.validator import SecurityValidator, SecurityError


@pytest.fixture
def base_security_config():
    """Create a basic security configuration."""
    return SecurityConfig(
        allowed_directory="/tmp/allowed",
        max_file_size_mb=10,
        allowed_file_extensions=[".txt", ".json"]
    )


@pytest.fixture
def temp_allowed_dir():
    """Create a temporary allowed directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def temp_session_dir():
    """Create a temporary session directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


class TestSessionAwareSecurityValidator:
    """Test cases for session-aware SecurityValidator."""
    
    def test_no_session_directory_uses_allowed_directory(self, base_security_config, temp_allowed_dir):
        """Test that without session directory, it uses the allowed directory."""
        # Update config with temp directory
        config = SecurityConfig(
            allowed_directory=temp_allowed_dir,
            max_file_size_mb=10,
            allowed_file_extensions=[".txt", ".json"]
        )
        
        validator = SecurityValidator(config)
        
        # Should use allowed directory when no session is set
        effective_dir = validator.get_effective_base_directory()
        assert str(effective_dir) == str(Path(temp_allowed_dir).resolve())
    
    def test_session_directory_overrides_allowed_directory(self, base_security_config, temp_allowed_dir, temp_session_dir):
        """Test that session directory takes precedence over allowed directory."""
        # Update config with temp directory
        config = SecurityConfig(
            allowed_directory=temp_allowed_dir,
            max_file_size_mb=10,
            allowed_file_extensions=[".txt", ".json"]
        )
        
        validator = SecurityValidator(config)
        
        # Set session directory
        session_path = Path(temp_session_dir)
        validator.set_session_directory(session_path)
        
        # Should use session directory when set
        effective_dir = validator.get_effective_base_directory()
        assert str(effective_dir) == str(session_path.resolve())
    
    def test_session_directory_none_resets_to_allowed(self, base_security_config, temp_allowed_dir, temp_session_dir):
        """Test that setting session directory to None resets to allowed directory."""
        # Update config with temp directory
        config = SecurityConfig(
            allowed_directory=temp_allowed_dir,
            max_file_size_mb=10,
            allowed_file_extensions=[".txt", ".json"]
        )
        
        validator = SecurityValidator(config)
        
        # Set and then clear session directory
        validator.set_session_directory(Path(temp_session_dir))
        validator.set_session_directory(None)
        
        # Should revert to allowed directory
        effective_dir = validator.get_effective_base_directory()
        assert str(effective_dir) == str(Path(temp_allowed_dir).resolve())
    
    def test_path_resolution_with_session_directory(self, base_security_config, temp_session_dir):
        """Test path resolution with session directory."""
        validator = SecurityValidator(base_security_config)
        validator.set_session_directory(Path(temp_session_dir))
        
        # Create test file in session directory
        test_file = Path(temp_session_dir) / "test.txt"
        test_file.write_text("test content")
        
        # Relative path should resolve against session directory
        resolved_path = validator._resolve_path("test.txt")
        assert resolved_path == test_file.resolve()
    
    def test_file_validation_with_session_directory(self, base_security_config, temp_session_dir):
        """Test file validation with session directory."""
        # Update config to allow temp session dir
        config = SecurityConfig(
            allowed_directory=temp_session_dir,
            max_file_size_mb=10,
            allowed_file_extensions=[".txt", ".json"]
        )
        
        validator = SecurityValidator(config)
        validator.set_session_directory(Path(temp_session_dir))
        
        # Create test file in session directory
        test_file = Path(temp_session_dir) / "test.txt"
        test_file.write_text("test content")
        
        # Should validate successfully
        validated_path = validator.validate_file_path("test.txt")
        assert validated_path == test_file.resolve()
    
    def test_directory_validation_with_session_directory(self, base_security_config, temp_session_dir):
        """Test directory validation with session directory."""
        # Update config to allow temp session dir
        config = SecurityConfig(
            allowed_directory=temp_session_dir,
            max_file_size_mb=10,
            allowed_file_extensions=[".txt", ".json"]
        )
        
        validator = SecurityValidator(config)
        validator.set_session_directory(Path(temp_session_dir))
        
        # Create test subdirectory in session directory
        test_subdir = Path(temp_session_dir) / "subdir"
        test_subdir.mkdir()
        
        # Should validate successfully
        validated_path = validator.validate_directory_path("subdir")
        assert validated_path == test_subdir.resolve()
    
    def test_session_directory_blocks_access_outside_session(self, base_security_config, temp_session_dir):
        """Test that session directory blocks access outside session scope."""
        validator = SecurityValidator(base_security_config)
        validator.set_session_directory(Path(temp_session_dir))
        
        # Try to access file outside session directory (should fail)
        with tempfile.NamedTemporaryFile(suffix=".txt") as temp_file:
            with pytest.raises(SecurityError, match="not in allowed directories"):
                validator.validate_file_path(temp_file.name)
    
    def test_security_info_includes_session_info(self, base_security_config, temp_session_dir):
        """Test that security info includes session information."""
        validator = SecurityValidator(base_security_config)
        
        # Without session
        info = validator.get_security_info()
        assert info["session_directory"] is None
        assert info["effective_base_directory"] == info["allowed_directory"]
        
        # With session
        validator.set_session_directory(Path(temp_session_dir))
        info = validator.get_security_info()
        assert info["session_directory"] == str(Path(temp_session_dir))
        assert info["effective_base_directory"] == str(Path(temp_session_dir))
    
    def test_absolute_paths_still_work_with_sessions(self, base_security_config, temp_session_dir):
        """Test that absolute paths still work with sessions (if within allowed area)."""
        # Update config to allow temp session dir
        config = SecurityConfig(
            allowed_directory=temp_session_dir,
            max_file_size_mb=10,
            allowed_file_extensions=[".txt", ".json"]
        )
        
        validator = SecurityValidator(config)
        validator.set_session_directory(Path(temp_session_dir))
        
        # Create test file
        test_file = Path(temp_session_dir) / "test.txt"
        test_file.write_text("test content")
        
        # Absolute path should work if within allowed area
        validated_path = validator.validate_file_path(str(test_file))
        assert validated_path == test_file.resolve()
    
    def test_path_traversal_blocked_in_session(self, base_security_config, temp_session_dir):
        """Test that path traversal is blocked even in session context."""
        validator = SecurityValidator(base_security_config)
        validator.set_session_directory(Path(temp_session_dir))
        
        # Try path traversal (should be blocked)
        with pytest.raises(SecurityError):
            validator.validate_file_path("../../../etc/passwd")