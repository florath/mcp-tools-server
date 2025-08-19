"""Tests for file_reader tool."""

import asyncio
import json
import pytest
from pathlib import Path

from src.mcp_tools_server.core.config import load_config
from src.mcp_tools_server.security.validator import SecurityValidator
from src.mcp_tools_server.tools.file_reader import FileReaderTool


@pytest.fixture
def config():
    """Load test configuration."""
    config_path = Path("config/server_config.json")
    return load_config(str(config_path))


@pytest.fixture
def security_validator(config):
    """Create security validator."""
    return SecurityValidator(config.security)


@pytest.fixture
def file_reader(security_validator):
    """Create file reader tool."""
    return FileReaderTool(security_validator=security_validator)


@pytest.mark.asyncio
async def test_file_reader_basic(file_reader):
    """Test basic file reading functionality."""
    # Create test file
    test_file = Path("/tmp/workspace/test_basic.txt")
    test_content = "Hello, World!\nThis is a test file."
    
    with open(test_file, 'w') as f:
        f.write(test_content)
    
    try:
        # Test reading
        params = {"file_path": str(test_file)}
        result = await file_reader.execute(params)
        
        assert result["content"] == test_content
        assert result["encoding"] == "utf-8"
        assert "size_bytes" in result
        
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()


@pytest.mark.asyncio
async def test_file_reader_with_line_numbers(file_reader):
    """Test file reading with line numbers."""
    test_file = Path("/tmp/workspace/test_lines.txt")
    test_content = "Line 1\nLine 2\nLine 3"
    
    with open(test_file, 'w') as f:
        f.write(test_content)
    
    try:
        params = {
            "file_path": str(test_file),
            "include_line_numbers": True
        }
        result = await file_reader.execute(params)
        
        assert result["content"] == test_content
        assert "content_with_line_numbers" in result
        assert "   1: Line 1" in result["content_with_line_numbers"]
        
    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.asyncio
async def test_file_reader_security_error(file_reader):
    """Test security validation."""
    # Try to read file outside allowed directories
    params = {"file_path": "/etc/passwd"}
    
    with pytest.raises(ValueError, match="Security error"):
        await file_reader.execute(params)


if __name__ == "__main__":
    # Run a simple test
    async def run_test():
        from src.mcp_tools_server.core.config import Config, SecurityConfig
        
        # Create simple config for testing
        security_config = SecurityConfig(
            allowed_directories=["/tmp/workspace"],
            max_file_size_mb=1,
            allowed_file_extensions=[".json", ".txt"]
        )
        
        validator = SecurityValidator(security_config)
        tool = FileReaderTool(security_validator=validator)
        
        # Test with the test config file
        params = {"file_path": "/tmp/workspace/test_config.json"}
        result = await tool.execute(params)
        
        print("✅ File reader test successful!")
        print(f"File: {result['file_path']}")
        print(f"Size: {result['size_bytes']} bytes")
        print("Content preview:")
        content = json.loads(result['content'])
        print(json.dumps(content, indent=2))
    
    asyncio.run(run_test())