"""Configuration management for MCP tools server."""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = "127.0.0.1"
    port: int = 7091
    debug: bool = False


class SecurityConfig(BaseModel):
    """Security configuration."""
    max_file_size_mb: int = 100
    allowed_file_extensions: List[str] = Field(default_factory=list)
    allowed_directory: Optional[str] = None
    """If set, all session directories must be within this path.
    Prevents the REST API from being used to access arbitrary filesystem locations.
    When omitted, any existing directory may be used as a session root."""


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"


class SessionsConfig(BaseModel):
    """Sessions configuration."""
    timeout_seconds: int = 3600  # 1 hour default
    max_sessions: int = 100


class ToolsConfig(BaseModel):
    """Tools configuration."""
    read_file: Dict[str, Any] = Field(default_factory=dict)
    write_file: Dict[str, Any] = Field(default_factory=dict)
    remove_file: Dict[str, Any] = Field(default_factory=dict)
    move_file: Dict[str, Any] = Field(default_factory=dict)
    edit_file: Dict[str, Any] = Field(default_factory=dict)
    find_files: Dict[str, Any] = Field(default_factory=dict)
    search_content: Dict[str, Any] = Field(default_factory=dict)
    list_dir: Dict[str, Any] = Field(default_factory=dict)
    mkdir: Dict[str, Any] = Field(default_factory=dict)
    rmdir: Dict[str, Any] = Field(default_factory=dict)
    dir_exists: Dict[str, Any] = Field(default_factory=dict)


class Config(BaseModel):
    """Main configuration."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    sessions: SessionsConfig = Field(default_factory=SessionsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)


def load_config(config_path: str) -> Config:
    """Load configuration from JSON file."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

    return Config(**config_data)
