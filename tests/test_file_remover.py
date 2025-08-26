"""Tests for file_remover tool."""

import asyncio
import json
import pytest
import tempfile
import os
from pathlib import Path

from src.mcp_tools_server.core.config import load_config
from src.mcp_tools_server.security.validator import SecurityValidator
from src.mcp_tools_server.tools.file_remover import FileRemoverTool


@pytest.fixture
def config():
    """Load test configuration."""
    config_path = Path("config/server_config.json")
    return load_config(str(config_path))


@pytest.fixture
def security_validator(config):
    """Create security validator with temp directory."""
    # Use a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Override the allowed directory for testing
        config.security.allowed_directory = temp_dir
        validator = SecurityValidator(config.security)
        yield validator


@pytest.fixture
def file_remover(security_validator):
    """Create file remover tool."""
    return FileRemoverTool(security_validator=security_validator)


@pytest.fixture
def test_file(security_validator):
    """Create a test file in the allowed directory."""
    allowed_dir = Path(security_validator.allowed_dir)
    test_file = allowed_dir / "test_file.txt"
    test_file.write_text("Test content for removal")
    return test_file


@pytest.mark.asyncio
async def test_file_remover_basic_removal(file_remover, test_file):
    """Test basic file removal."""
    params = {
        "file_path": str(test_file),
        "reason": "Testing basic file removal functionality"
    }
    
    result = await file_remover.execute(params)
    
    assert result["file_path"] == str(test_file)
    assert result["size_bytes"] > 0
    assert result["backup_created"] is False
    assert result["force_used"] is False
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_file_remover_with_backup(file_remover, test_file):
    """Test file removal with backup creation."""
    params = {
        "file_path": str(test_file),
        "create_backup": True,
        "reason": "Testing file removal with backup creation"
    }
    
    result = await file_remover.execute(params)
    
    assert result["backup_created"] is True
    assert result["backup_path"] is not None
    assert not test_file.exists()
    
    # Verify backup exists
    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert backup_path.read_text() == "Test content for removal"


@pytest.mark.asyncio
async def test_file_remover_with_force(file_remover, test_file):
    """Test file removal with force flag."""
    # Make file read-only to test force behavior
    test_file.chmod(0o444)
    
    params = {
        "file_path": str(test_file),
        "force": True,
        "reason": "Testing file removal with force flag"
    }
    
    result = await file_remover.execute(params)
    
    assert result["force_used"] is True
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_file_remover_nonexistent_file(file_remover):
    """Test removal of nonexistent file."""
    params = {
        "file_path": "/nonexistent/file.txt",
        "reason": "Testing removal of nonexistent file"
    }
    
    with pytest.raises(ValueError, match="File does not exist"):
        await file_remover.execute(params)


@pytest.mark.asyncio
async def test_file_remover_missing_reason(file_remover, test_file):
    """Test file removal without mandatory reason parameter."""
    params = {
        "file_path": str(test_file)
        # Missing reason parameter
    }
    
    # Note: The reason validation is handled by the base tool schema
    # This test verifies the parameter schema includes the reason field
    schema = file_remover.get_parameters_schema()
    info = file_remover.get_info()
    
    assert "reason" in info["parameters"]["required"]
    assert info["parameters"]["properties"]["reason"]["minLength"] == 10


@pytest.mark.asyncio
async def test_file_remover_directory_not_file(file_remover, security_validator):
    """Test removal of directory instead of file."""
    allowed_dir = Path(security_validator.allowed_dir)
    test_dir = allowed_dir / "test_directory"
    test_dir.mkdir()
    
    params = {
        "file_path": str(test_dir),
        "reason": "Testing directory removal attempt"
    }
    
    with pytest.raises(ValueError, match="Path is not a file"):
        await file_remover.execute(params)


def test_file_remover_schema():
    """Test file remover parameter schema."""
    tool = FileRemoverTool()
    schema = tool.get_parameters_schema()
    
    assert schema["type"] == "object"
    assert "file_path" in schema["required"]
    assert "force" in schema["properties"]
    assert "create_backup" in schema["properties"]
    assert schema["properties"]["force"]["default"] is False
    assert schema["properties"]["create_backup"]["default"] is False


def test_file_remover_tool_info():
    """Test file remover tool info includes reason parameter."""
    tool = FileRemoverTool()
    info = tool.get_info()
    
    assert info["name"] == "file_remover"
    assert "reason" in info["parameters"]["required"]
    assert info["parameters"]["properties"]["reason"]["minLength"] == 10