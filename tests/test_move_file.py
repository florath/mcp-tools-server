"""Tests for move_file tool."""

import asyncio
import json
import pytest
import tempfile
import os
from pathlib import Path

from src.mcp_tools_server.core.config import load_config
from src.mcp_tools_server.security.validator import SecurityValidator
from src.mcp_tools_server.tools.move_file import MoveFileTool


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
def move_file(security_validator):
    """Create file mover tool."""
    return FileMoverTool(security_validator=security_validator)


@pytest.fixture
def test_file(security_validator):
    """Create a test file in the allowed directory."""
    allowed_dir = Path(security_validator.allowed_dir)
    test_file = allowed_dir / "test_file.txt"
    test_file.write_text("Test content for moving")
    return "test_file.txt"  # Return relative path


@pytest.fixture
def existing_destination(security_validator):
    """Create an existing destination file."""
    allowed_dir = Path(security_validator.allowed_dir)
    dest_file = allowed_dir / "existing_dest.txt"
    dest_file.write_text("Existing destination content")
    return "existing_dest.txt"  # Return relative path


@pytest.mark.asyncio
async def test_move_file_basic_move(file_mover, test_file, security_validator):
    """Test basic file move/rename."""
    allowed_dir = Path(security_validator.allowed_dir)
    destination = "moved_file.txt"
    
    params = {
        "source_path": test_file,
        "destination_path": destination,
        "reason": "Testing basic file move functionality"
    }
    
    result = await move_file.execute(params)
    
    assert result["source_path"] == test_file
    assert result["destination_path"] == destination
    assert result["size_bytes"] > 0
    assert result["overwrite_used"] is False
    assert result["backup_created"] is False
    assert not (allowed_dir / test_file).exists()
    assert (allowed_dir / destination).exists()
    assert (allowed_dir / destination).read_text() == "Test content for moving"


@pytest.mark.asyncio
async def test_move_file_to_subdirectory(file_mover, test_file, security_validator):
    """Test moving file to a subdirectory (auto-create)."""
    allowed_dir = Path(security_validator.allowed_dir)
    destination = "subdir/moved_file.txt"
    
    params = {
        "source_path": test_file,
        "destination_path": destination,
        "reason": "Testing file move to new subdirectory"
    }
    
    result = await move_file.execute(params)
    
    assert not (allowed_dir / test_file).exists()
    assert (allowed_dir / destination).exists()
    assert (allowed_dir / "subdir").exists()  # subdirectory was created
    assert (allowed_dir / destination).read_text() == "Test content for moving"


@pytest.mark.asyncio
async def test_move_file_overwrite_with_backup(file_mover, test_file, existing_destination, security_validator):
    """Test file move with overwrite and backup."""
    allowed_dir = Path(security_validator.allowed_dir)
    
    params = {
        "source_path": test_file,
        "destination_path": existing_destination,
        "overwrite": True,
        "create_backup": True,
        "reason": "Testing file move with overwrite and backup"
    }
    
    result = await move_file.execute(params)
    
    assert result["overwrite_used"] is True
    assert result["backup_created"] is True
    assert result["backup_path"] is not None
    assert not (allowed_dir / test_file).exists()
    assert (allowed_dir / existing_destination).exists()
    assert (allowed_dir / existing_destination).read_text() == "Test content for moving"
    
    # Verify backup exists with original content
    backup_path = allowed_dir / result["backup_path"]
    assert backup_path.exists()
    assert backup_path.read_text() == "Existing destination content"


@pytest.mark.asyncio
async def test_move_file_overwrite_without_backup(file_mover, test_file, existing_destination, security_validator):
    """Test file move with overwrite but no backup."""
    allowed_dir = Path(security_validator.allowed_dir)
    
    params = {
        "source_path": test_file,
        "destination_path": existing_destination,
        "overwrite": True,
        "reason": "Testing file move with overwrite but no backup"
    }
    
    result = await move_file.execute(params)
    
    assert result["overwrite_used"] is True
    assert result["backup_created"] is False
    assert result["backup_path"] is None
    assert not (allowed_dir / test_file).exists()
    assert (allowed_dir / existing_destination).exists()
    assert (allowed_dir / existing_destination).read_text() == "Test content for moving"


@pytest.mark.asyncio
async def test_move_file_no_overwrite_fails(file_mover, test_file, existing_destination, security_validator):
    """Test file move fails when destination exists and overwrite is False."""
    allowed_dir = Path(security_validator.allowed_dir)
    
    params = {
        "source_path": test_file,
        "destination_path": existing_destination,
        "overwrite": False,  # Default
        "reason": "Testing file move failure when destination exists"
    }
    
    with pytest.raises(ValueError, match="Destination file already exists"):
        await move_file.execute(params)
    
    # Verify files unchanged
    assert (allowed_dir / test_file).exists()
    assert (allowed_dir / existing_destination).exists()
    assert (allowed_dir / existing_destination).read_text() == "Existing destination content"


@pytest.mark.asyncio
async def test_move_file_nonexistent_source(file_mover, security_validator):
    """Test move of nonexistent source file."""
    nonexistent = "nonexistent.txt"
    destination = "dest.txt"
    
    params = {
        "source_path": nonexistent,
        "destination_path": destination,
        "reason": "Testing move of nonexistent source file"
    }
    
    with pytest.raises(ValueError, match="Security error.*does not exist"):
        await move_file.execute(params)


@pytest.mark.asyncio
async def test_move_file_directory_as_source(file_mover, security_validator):
    """Test move of directory instead of file."""
    allowed_dir = Path(security_validator.allowed_dir)
    test_dir = allowed_dir / "test_directory"
    test_dir.mkdir()
    destination = "dest.txt"
    
    params = {
        "source_path": "test_directory",
        "destination_path": destination,
        "reason": "Testing directory move attempt"
    }
    
    with pytest.raises(ValueError, match="Security error.*is not a file"):
        await move_file.execute(params)


@pytest.mark.asyncio
async def test_move_file_missing_parameters(move_file):
    """Test file mover with missing required parameters."""
    # Missing destination_path
    params = {
        "source_path": "some/path.txt",
        "reason": "Testing missing destination parameter"
    }
    
    with pytest.raises(ValueError, match="destination_path parameter is required"):
        await move_file.execute(params)
    
    # Missing source_path
    params = {
        "destination_path": "some/dest.txt",
        "reason": "Testing missing source parameter"
    }
    
    with pytest.raises(ValueError, match="source_path parameter is required"):
        await move_file.execute(params)


def test_move_file_schema():
    """Test file mover parameter schema."""
    tool = FileMoverTool()
    schema = tool.get_parameters_schema()
    
    assert schema["type"] == "object"
    assert "source_path" in schema["required"]
    assert "destination_path" in schema["required"]
    assert "overwrite" in schema["properties"]
    assert "create_backup" in schema["properties"]
    assert schema["properties"]["overwrite"]["default"] is False
    assert schema["properties"]["create_backup"]["default"] is False


def test_move_file_tool_info():
    """Test file mover tool info includes reason parameter."""
    tool = FileMoverTool()
    info = tool.get_info()
    
    assert info["name"] == "move_file"
    assert "reason" in info["parameters"]["required"]
    assert info["parameters"]["properties"]["reason"]["minLength"] == 10


@pytest.mark.asyncio
async def test_move_file_rename_in_same_directory(file_mover, test_file, security_validator):
    """Test renaming file in same directory."""
    allowed_dir = Path(security_validator.allowed_dir)
    new_name = "renamed_file.txt"
    
    params = {
        "source_path": test_file,
        "destination_path": new_name,
        "reason": "Testing file rename in same directory"
    }
    
    result = await move_file.execute(params)
    
    assert not (allowed_dir / test_file).exists()
    assert (allowed_dir / new_name).exists()
    assert (allowed_dir / new_name).read_text() == "Test content for moving"
    assert result["source_path"] == test_file
    assert result["destination_path"] == new_name