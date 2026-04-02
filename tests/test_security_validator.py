"""Tests for SecurityValidator."""

import pytest
import tempfile
from pathlib import Path

from mcp_tools_server.core.config import SecurityConfig
from mcp_tools_server.security.validator import SecurityValidator, SecurityError


class TestSecurityValidator:
    """Test cases for SecurityValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = SecurityConfig(
            allowed_file_extensions=[".txt", ".json"],
            max_file_size_mb=100
        )
        self.validator = SecurityValidator(self.config)
        self.token = self.validator.set_session_directory(self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        self.validator.reset_session_directory(self.token)
        if self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)

    def test_security_info(self):
        """Test security info includes session information."""
        info = self.validator.get_security_info()
        assert "session_directory" in info

    def test_security_info_contains_extensions(self):
        """Test security info contains allowed extensions."""
        info = self.validator.get_security_info()
        assert "allowed_extensions" in info

    def test_file_validation_fails_outside_session(self):
        """Test that validation fails for paths outside session."""
        with pytest.raises(SecurityError):
            self.validator.validate_file_path("/etc/passwd")

    def test_path_traversal_blocked(self):
        """Test that path traversal is blocked."""
        with pytest.raises(SecurityError):
            self.validator.validate_file_path("../../../etc/passwd")
