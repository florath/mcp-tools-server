"""Shared fixtures for MCP Tools Server tests."""

import asyncio
import pytest
from pathlib import Path
from contextlib import asynccontextmanager

from mcp_tools_server.core.config import load_config, Config, SecurityConfig, ServerConfig, LoggingConfig, ToolsConfig
from mcp_tools_server.security.validator import SecurityValidator


@pytest.fixture(scope="session")
def test_workspace_dir(tmp_path_factory) -> Path:
    """Create a shared test workspace directory."""
    workspace = tmp_path_factory.mktemp("workspace")
    (workspace / "subdir").mkdir()
    return workspace


@pytest.fixture
def temp_workspace(tmp_path) -> Path:
    """Create a temporary workspace directory for test."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "subdir").mkdir()
    return workspace


@pytest.fixture
def config(temp_workspace) -> Config:
    """Create test configuration."""
    return Config(
        server=ServerConfig(host="127.0.0.1", port=7091, debug=True),
        security=SecurityConfig(
            allowed_file_extensions=[".json", ".yaml", ".yml", ".txt", ".py", ".js", ".ts",
                                     ".md", ".csv", ".xml", ".html", ".css", ".sql", ".toml",
                                     ".cfg", ".ini", ".conf", ".sh", ".bat", ".dockerfile",
                                     ".dockerignore", ".gitignore", ".env", ".lock"],
            max_file_size_mb=100
        ),
        logging=LoggingConfig(level="INFO", format="standard"),
        tools=ToolsConfig()
    )


@pytest.fixture
def security_validator(config, temp_workspace) -> SecurityValidator:
    """Create security validator with active session context."""
    validator = SecurityValidator(config.security)
    token = validator.set_session_directory(temp_workspace)
    try:
        yield validator
    finally:
        validator.reset_session_directory(token)


@asynccontextmanager
async def active_session(validator: SecurityValidator, temp_workspace: Path):
    """Context manager for establishing active session in tests."""
    token = validator.set_session_directory(temp_workspace)
    try:
        yield temp_workspace
    finally:
        validator.reset_session_directory(token)


@pytest.fixture
def test_file_content() -> str:
    """Sample content for test files."""
    return "Hello, World!\nThis is a test file.\nLine 3"


@pytest.fixture
def sample_json_content() -> dict:
    """Sample JSON content for tests."""
    return {"key": "value", "number": 42, "list": [1, 2, 3]}


@pytest.fixture
def temp_directory(tmp_path) -> str:
    """Create a temporary directory for testing (for tests expecting string path)."""
    return str(tmp_path / "temp_test_dir")
