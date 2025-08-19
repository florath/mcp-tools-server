"""Configuration management for MCP tools server."""

import json
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration."""
    host: str = "127.0.0.1"
    port: int = 7091
    debug: bool = False


class SecurityConfig(BaseModel):
    """Security configuration."""
    allowed_directories: List[str] = Field(default_factory=list)
    max_file_size_mb: int = 100
    allowed_file_extensions: List[str] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"


class ToolsConfig(BaseModel):
    """Tools configuration."""
    file_reader: Dict[str, Any] = Field(default_factory=dict)
    file_writer: Dict[str, Any] = Field(default_factory=dict)
    python_linter: Dict[str, Any] = Field(default_factory=dict)
    directory_manager: Dict[str, Any] = Field(default_factory=dict)
    file_editor: Dict[str, Any] = Field(default_factory=dict)
    file_finder: Dict[str, Any] = Field(default_factory=dict)
    content_searcher: Dict[str, Any] = Field(default_factory=dict)
    python_runner: Dict[str, Any] = Field(default_factory=dict)


class Config(BaseModel):
    """Main configuration."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)


def load_config(config_path: str) -> Config:
    """Load configuration from JSON file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    return Config(**config_data)