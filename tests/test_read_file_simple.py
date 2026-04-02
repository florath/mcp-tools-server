"""Tests for read_file tool."""

import pytest
import tempfile
from pathlib import Path

from mcp_tools_server.core.config import Config, SecurityConfig
from mcp_tools_server.security.validator import SecurityValidator
from mcp_tools_server.tools.read_file import ReadFileTool


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    import shutil
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def validator(temp_dir):
    """Create security validator with active session."""
    config = SecurityConfig(
        allowed_file_extensions=[".json", ".yaml", ".yml", ".txt", ".py", ".js", ".ts",
                                 ".md", ".csv", ".xml", ".html", ".css", ".sql", ".toml"],
        max_file_size_mb=100
    )
    validator = SecurityValidator(config)
    token = validator.set_session_directory(temp_dir)
    try:
        yield validator
    finally:
        validator.reset_session_directory(token)


@pytest.fixture
def read_file(validator):
    """Create file reader tool."""
    return ReadFileTool(security_validator=validator)


@pytest.mark.asyncio
async def test_read_file_basic(read_file, temp_dir):
    """Test basic file reading functionality."""
    test_file = temp_dir / "test_basic.txt"
    test_content = "Hello, World!\nThis is a test file."
    test_file.write_text(test_content)

    try:
        params = {"file_path": str(test_file), "reason": "Testing basic file reading"}
        result = await read_file.execute(params)

        assert result["content"] == test_content
        assert result["encoding"] == "utf-8"
        assert "size_bytes" in result

    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.asyncio
async def test_read_file_security_error(read_file):
    """Test security validation - try to read outside allowed directory."""
    params = {"file_path": "/etc/passwd", "reason": "Testing security validation"}

    with pytest.raises(ValueError, match="Security error|not in allowed"):
        await read_file.execute(params)


def test_read_file_schema(read_file):
    """Test tool schema generation."""
    schema = read_file.get_parameters_schema()

    assert "type" in schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "file_path" in schema["properties"]
    assert "required" in schema
    assert "file_path" in schema["required"]
