"""Tests for read_file tool."""

import pytest
from mcp_tools_server.tools.read_file import ReadFileTool


@pytest.fixture
def read_file():
    """Create file reader tool."""
    from mcp_tools_server.core.config import SecurityConfig
    from mcp_tools_server.security.validator import SecurityValidator
    config = SecurityConfig(
        allowed_file_extensions=[".json", ".yaml", ".yml", ".txt", ".py", ".js", ".ts",
                                 ".md", ".csv", ".xml", ".html", ".css", ".sql", ".toml"],
        max_file_size_mb=100
    )
    validator = SecurityValidator(config)
    return ReadFileTool(security_validator=validator)


def test_read_file_schema(read_file):
    """Test tool schema generation."""
    schema = read_file.get_parameters_schema()
    assert "type" in schema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "file_path" in schema["properties"]


def test_read_file_tool_info(read_file):
    """Test tool information retrieval."""
    info = read_file.get_info()
    assert "name" in info
    assert info["name"] == "read_file"
    assert "description" in info
