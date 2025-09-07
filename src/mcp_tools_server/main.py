"""Main entry point for MCP Tools Server."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import uvicorn

from .core.config import load_config
from .core.server import MCPToolsServer
from .core.structured_logger import logger


def setup_logging(config):
    """Setup logging configuration."""
    log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
    
    # Set log level on our structured logger
    logger.logger.setLevel(log_level)
    
    # Configure uvicorn logging to use our structured format
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.WARNING)  # Reduce uvicorn noise
    
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.WARNING)  # Reduce access log noise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MCP Tools Server")
    parser.add_argument(
        "--config", 
        default="config/server_config.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--host",
        help="Override host from config"
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Override port from config"
    )
    parser.add_argument(
        "--allowed-directory",
        help="Override allowed directory from config"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override log level (DEBUG, INFO, WARNING, ERROR)"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        sys.exit(1)
    
    # Override config with command line args
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    if args.allowed_directory:
        config.security.allowed_directory = args.allowed_directory
    if args.log_level:
        config.logging.level = args.log_level
    
    # Setup logging
    setup_logging(config)
    
    logger.server_event(f"Starting MCP Tools Server on {config.server.host}:{config.server.port}")
    logger.server_event(f"Security: allowed directory = {config.security.allowed_directory or 'unrestricted'}")
    
    # Create server
    try:
        mcp_server = MCPToolsServer(config)
        logger.server_event(f"Server created successfully")
        
        # Run server
        uvicorn.run(
            mcp_server.app,
            host=config.server.host,
            port=config.server.port,
            log_level="warning",  # Reduce uvicorn noise
            access_log=False  # Disable access logs to avoid mixed formats
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()